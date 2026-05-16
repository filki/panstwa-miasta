"""Tests for optional Redis backend."""

from __future__ import annotations

import pytest

from panstwa_miasta.db_redis import connect_redis, redis_configured, redis_ping


@pytest.mark.asyncio
async def test_redis_not_configured_by_default():
    """Without REDIS_URL, redis should not be configured."""
    assert not redis_configured()
    conn = await connect_redis()
    assert conn is None
    assert not await redis_ping()


@pytest.mark.asyncio
async def test_redis_connect_with_url(monkeypatch):
    """With REDIS_URL set, should connect and ping successfully."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    assert redis_configured()
    conn = await connect_redis()
    assert conn is not None
