"""Async database connections: local ``aiosqlite`` or Turso embedded replica."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite


def libsql_configured() -> bool:
    return bool(
        os.environ.get("LIBSQL_URL", "").strip() and os.environ.get("LIBSQL_AUTH_TOKEN", "").strip()
    )


def _db_path() -> Path:
    from panstwa_miasta.db import DB_PATH

    return DB_PATH


class _LibsqlRow(dict[str, Any]):
    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _LibsqlCursor:
    def __init__(self, rows: list[_LibsqlRow], lastrowid: int | None) -> None:
        self._rows = rows
        self.lastrowid = lastrowid

    async def fetchone(self) -> _LibsqlRow | None:
        return self._rows[0] if self._rows else None

    async def fetchall(self) -> list[_LibsqlRow]:
        return self._rows

    async def __aenter__(self) -> _LibsqlCursor:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _LibsqlConnection:
    def __init__(self, conn: Any) -> None:
        self._conn = conn
        self.row_factory: type | None = None

    def _rows_from_cursor(self, cursor: Any) -> list[_LibsqlRow]:
        if cursor.description is None:
            return []
        columns = [col[0] for col in cursor.description]
        return [_LibsqlRow(zip(columns, row, strict=True)) for row in cursor.fetchall()]

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> _LibsqlCursor:
        def run() -> tuple[list[_LibsqlRow], int | None]:
            cursor = self._conn.execute(sql, tuple(params))
            rows = self._rows_from_cursor(cursor)
            return rows, cursor.lastrowid

        rows, lastrowid = await asyncio.to_thread(run)
        return _LibsqlCursor(rows, lastrowid)

    async def executemany(self, sql: str, params: Iterable[Sequence[Any]]) -> None:
        def run() -> None:
            self._conn.executemany(sql, [tuple(row) for row in params])

        await asyncio.to_thread(run)

    async def commit(self) -> None:
        await asyncio.to_thread(self._conn.commit)

    async def close(self) -> None:
        await asyncio.to_thread(self._conn.close)


@asynccontextmanager
async def connect() -> AsyncIterator[Any]:
    if libsql_configured():
        import libsql

        sync_url = os.environ["LIBSQL_URL"].strip()
        auth_token = os.environ["LIBSQL_AUTH_TOKEN"].strip()
        local_path = _db_path()
        sync_interval = int(os.environ.get("LIBSQL_SYNC_INTERVAL", "60") or "60")

        def open_connection() -> Any:
            connect_fn = getattr(libsql, "connect")
            return connect_fn(
                str(local_path),
                sync_url=sync_url,
                auth_token=auth_token,
                sync_interval=sync_interval,
            )

        conn = await asyncio.to_thread(open_connection)
        wrapper = _LibsqlConnection(conn)
        try:
            yield wrapper
        finally:
            await wrapper.close()
    else:
        async with aiosqlite.connect(_db_path()) as db:
            yield db
