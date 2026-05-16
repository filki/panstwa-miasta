"""Optional Redis backend for runtime game state.

Feature flag: REDIS_URL env var. When set, Redis is used for room/player
state, rate limiting, appeal tokens, and share snapshots instead of SQLite.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable
from typing import cast

import redis.asyncio as aioredis

_pool: aioredis.Redis | None = None


def redis_configured() -> bool:
    """True if REDIS_URL is set and non-empty."""
    url = (os.environ.get("REDIS_URL") or "").strip()
    return bool(url)


async def connect_redis() -> aioredis.Redis | None:
    """Create connection pool from REDIS_URL env var.

    Returns None if REDIS_URL is not configured.
    """
    global _pool
    if not redis_configured():
        return None
    if _pool is not None:
        return _pool
    url = os.environ["REDIS_URL"].strip()
    _pool = aioredis.from_url(url, decode_responses=True)
    return _pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def redis_ping() -> bool:
    """True if Redis is connected and responsive."""
    r = await connect_redis()
    if r is None:
        return False
    try:
        return await cast(Awaitable[bool], r.ping())
    except Exception:
        return False
