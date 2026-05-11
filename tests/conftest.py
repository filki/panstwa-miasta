"""Shared pytest fixtures.

Isolates SQLite from any developer-local `panstwa_miasta.db` by redirecting
`db.DB_PATH` to a per-session temp file and initializing the schema before any
test runs.
"""

from __future__ import annotations

import asyncio

import pytest

from panstwa_miasta import db


@pytest.fixture(autouse=True)
def _isolated_test_db(tmp_path: object):
    """Fresh, isolated SQLite database per test.

    Function-scoped so `test_db_lifecycle` (which creates/deletes the DB
    itself) cannot corrupt sibling tests.
    """
    test_db = tmp_path / "test.db"  # type: ignore[operator]
    db.DB_PATH = test_db
    asyncio.run(db.init_db())
    yield
