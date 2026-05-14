"""Shared pytest fixtures.

Isolates SQLite from any developer-local `panstwa_miasta.db` by redirecting
`db.DB_PATH` to a per-session temp file and initializing the schema before any
test runs.
"""

from __future__ import annotations

import asyncio

import pytest

from panstwa_miasta import data, db


@pytest.fixture(autouse=True)
def _isolated_test_db(tmp_path: object, monkeypatch: pytest.MonkeyPatch):
    """Fresh, isolated SQLite database per test.

    Function-scoped so `test_db_lifecycle` (which creates/deletes the DB
    itself) cannot corrupt sibling tests. Also primes the in-memory
    ``data.COUNTRIES``, ``data.MIASTA``, ``data.NAMES`` i ``data.JOBS`` z tabel
    ``countries``, ``cities``, ``names``, ``jobs`` oraz ``ZWIERZETA`` / ``ROSLINY``
    (flora pod polem „Roślina” — moduły seed, nie SQL).
    """
    test_db = tmp_path / "test.db"  # type: ignore[operator]
    monkeypatch.delenv("LIBSQL_URL", raising=False)
    monkeypatch.delenv("LIBSQL_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("PM_DICTIONARY_LIBSQL_URL", raising=False)
    monkeypatch.delenv("PM_DICTIONARY_LIBSQL_AUTH_TOKEN", raising=False)
    db.DB_PATH = test_db
    asyncio.run(db.init_db())
    asyncio.run(data.reload_countries())
    asyncio.run(data.reload_miasta())
    asyncio.run(data.reload_names())
    asyncio.run(data.reload_jobs())
    asyncio.run(data.reload_things())
    asyncio.run(data.reload_zwierzeta())
    asyncio.run(data.reload_rosliny())
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limit_counters():
    from panstwa_miasta.appeal_tokens import clear_appeal_tokens_for_tests
    from panstwa_miasta.limits import reset_counters_for_tests

    clear_appeal_tokens_for_tests()
    reset_counters_for_tests()
    yield
