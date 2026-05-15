"""Batched seed for animal_norms / plant_norms (prod 502 after single executemany)."""

import pytest

from panstwa_miasta import db as db_module
from panstwa_miasta.db import init_db
from panstwa_miasta.db_backend import connect


@pytest.mark.asyncio
async def test_init_db_populates_animal_and_plant_norms(tmp_path: object, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "norms-seed.db")  # type: ignore[operator]
    await init_db()
    async with connect() as db:
        async with db.execute("SELECT COUNT(*) FROM animal_norms") as cur:
            animals = int((await cur.fetchone())[0])
        async with db.execute("SELECT COUNT(*) FROM plant_norms") as cur:
            plants = int((await cur.fetchone())[0])
    assert animals > 1000
    assert plants > 1000
