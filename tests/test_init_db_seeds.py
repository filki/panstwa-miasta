"""init_db skips dictionary seeds when tables already have rows (Turso restart path)."""

import pytest

from panstwa_miasta import db as db_module
from panstwa_miasta.db import _table_nonempty, init_db
from panstwa_miasta.db_backend import connect


@pytest.mark.asyncio
async def test_table_nonempty_false_on_empty_table(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "probe-empty.db")  # type: ignore[operator]
    async with connect() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS countries (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        await db.commit()
        assert not await _table_nonempty(db, "countries")


@pytest.mark.asyncio
async def test_table_nonempty_true_after_insert(tmp_path: object, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "probe-one.db")  # type: ignore[operator]
    async with connect() as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS countries (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        await db.execute("INSERT INTO countries (name) VALUES ('Polska')")
        await db.commit()
        assert await _table_nonempty(db, "countries")


@pytest.mark.asyncio
async def test_init_db_second_call_does_not_change_country_count():
    await init_db()
    async with connect() as db, db.execute("SELECT COUNT(*) FROM countries") as cur:
        first = int((await cur.fetchone())[0])

    await init_db()
    async with connect() as db, db.execute("SELECT COUNT(*) FROM countries") as cur:
        second = int((await cur.fetchone())[0])

    assert first == second
    assert first > 0
