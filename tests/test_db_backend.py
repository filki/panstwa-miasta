"""Testy dla db_backend.py — _LibsqlRow, _LibsqlCursor, _LibsqlConnection, connect()."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from panstwa_miasta.db_backend import (
    _db_path,
    _LibsqlConnection,
    _LibsqlCursor,
    _LibsqlRow,
    connect,
    connect_dictionary,
    dictionary_libsql_configured,
    libsql_configured,
)


class TestLibsqlConfigured:
    def test_libsql_configured_returns_false_when_env_missing(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert libsql_configured() is False

    def test_libsql_configured_returns_true_when_both_set(self) -> None:
        with patch.dict(
            os.environ,
            {"LIBSQL_URL": "https://turso.example.com", "LIBSQL_AUTH_TOKEN": "tok_abc"},
        ):
            assert libsql_configured() is True

    def test_libsql_configured_returns_false_when_only_url(self) -> None:
        with patch.dict(os.environ, {"LIBSQL_URL": "https://turso.example.com"}):
            assert libsql_configured() is False

    def test_dictionary_libsql_configured_false_by_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            assert dictionary_libsql_configured() is False


class TestDbPath:
    def test_db_path_returns_path(self) -> None:
        path = _db_path()
        assert str(path).endswith(".db") or str(path).endswith(".sqlite")


class TestLibsqlRow:
    def test_dict_access(self) -> None:
        row = _LibsqlRow({"name": "Polska", "code": "PL"})
        assert row["name"] == "Polska"
        assert row["code"] == "PL"

    def test_int_index(self) -> None:
        row = _LibsqlRow({"name": "Polska", "code": "PL"})
        assert row[0] == "Polska"
        assert row[1] == "PL"

    def test_missing_key(self) -> None:
        row = _LibsqlRow({"name": "Polska"})
        with pytest.raises(KeyError):
            _ = row["nonexistent"]


class TestLibsqlCursor:
    @pytest.mark.asyncio
    async def test_fetchone_returns_first(self) -> None:
        rows = [_LibsqlRow({"id": 1}), _LibsqlRow({"id": 2})]
        cursor = _LibsqlCursor(rows, lastrowid=5)
        result = await cursor.fetchone()
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_fetchone_returns_none_when_empty(self) -> None:
        cursor = _LibsqlCursor([], lastrowid=None)
        result = await cursor.fetchone()
        assert result is None

    @pytest.mark.asyncio
    async def test_fetchall_returns_all(self) -> None:
        rows = [_LibsqlRow({"id": 1}), _LibsqlRow({"id": 2})]
        cursor = _LibsqlCursor(rows, lastrowid=None)
        result = await cursor.fetchall()
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        cursor = _LibsqlCursor([], lastrowid=None)
        await cursor.close()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        cursor = _LibsqlCursor([_LibsqlRow({"x": 1})], lastrowid=None)
        async with cursor as c:
            result = await c.fetchone()
        assert result["x"] == 1

    def test_lastrowid_and_rowcount(self) -> None:
        cursor = _LibsqlCursor([], lastrowid=42, rowcount=3)
        assert cursor.lastrowid == 42
        assert cursor.rowcount == 3


class TestLibsqlConnection:
    def test_row_factory_can_be_set(self) -> None:
        conn = _LibsqlConnection(MagicMock())
        conn.row_factory = dict
        assert conn.row_factory is dict

    @pytest.mark.asyncio
    async def test_execute_returns_cursor(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",), ("name",)]
        mock_cursor.fetchall.return_value = [(1, "Ala")]
        mock_cursor.lastrowid = None
        mock_conn.execute.return_value = mock_cursor

        conn = _LibsqlConnection(mock_conn)
        async with conn.execute("SELECT 1") as cursor:
            assert cursor is not None

    @pytest.mark.asyncio
    async def test_execute_empty_description(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = None
        mock_cursor.fetchall.return_value = []
        mock_conn.execute.return_value = mock_cursor

        conn = _LibsqlConnection(mock_conn)
        async with conn.execute("DROP TABLE x") as cursor:
            assert cursor is not None

    @pytest.mark.asyncio
    async def test_executemany(self) -> None:
        mock_conn = MagicMock()
        conn = _LibsqlConnection(mock_conn)
        async with conn.executemany("INSERT INTO t VALUES (?)", [(1,), (2,)]) as cursor:
            assert cursor is not None

    @pytest.mark.asyncio
    async def test_commit(self) -> None:
        mock_conn = MagicMock()
        conn = _LibsqlConnection(mock_conn)
        await conn.commit()
        mock_conn.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        mock_conn = MagicMock()
        conn = _LibsqlConnection(mock_conn)
        await conn.close()
        mock_conn.close.assert_called_once()


class TestConnectFallback:
    """Test aiosqlite fallback path (no LIBSQL configured)."""

    @pytest.mark.asyncio
    async def test_connect_uses_aiosqlite_when_not_configured(self) -> None:
        mock_db = AsyncMock()  # async context manager
        mock_connect = MagicMock(return_value=mock_db)
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("panstwa_miasta.db_backend.aiosqlite.connect", mock_connect),
        ):
            async with connect() as _:
                pass
            mock_connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_dictionary_uses_aiosqlite_when_not_configured(self) -> None:
        mock_db = AsyncMock()
        mock_connect = MagicMock(return_value=mock_db)
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("panstwa_miasta.db_backend.aiosqlite.connect", mock_connect),
        ):
            async with connect_dictionary() as _:
                pass
            mock_connect.assert_called_once()
