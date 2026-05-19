"""Optional Redis backend for runtime game state.

Feature flag: REDIS_URL env var. When set, Redis is used for room/player
state, rate limiting, appeal tokens, and share snapshots instead of SQLite.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable
from typing import cast

_pool = None


def redis_configured() -> bool:
    url = (os.environ.get("REDIS_URL") or "").strip()
    return bool(url)


async def connect_redis():
    global _pool
    if not redis_configured():
        return None
    if _pool is not None:
        return _pool
    try:
        import redis.asyncio as aioredis
    except ImportError:
        return None
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


# ---------------------------------------------------------------------------
# Room persistence
# ---------------------------------------------------------------------------

ROOM_TTL = 86400  # 24h


def _room_key(room_id: str) -> str:
    return f"room:{room_id}"


def _scores_key(room_id: str) -> str:
    return f"room:{room_id}:scores"


def _active_key() -> str:
    return "room:active"


async def redis_save_room(
    room_id: str,
    max_rounds: int,
    time_limit: int,
    current_round: int,
    host_name: str,
    visibility: str = "public",
) -> None:
    """Save/update room state in Redis."""
    r = await connect_redis()
    if r is None:
        return
    key = _room_key(room_id)
    pipe = r.pipeline()
    pipe.hset(
        key,
        mapping={
            "max_rounds": max_rounds,
            "time_limit": time_limit,
            "current_round": current_round,
            "host_name": host_name,
            "visibility": visibility,
        },
    )
    pipe.sadd(_active_key(), room_id)
    pipe.expire(key, ROOM_TTL)
    await pipe.execute()


async def redis_fetch_room_snapshot(room_id: str) -> dict[str, object] | None:
    """Return room data + players, or None if missing."""
    r = await connect_redis()
    if r is None:
        return None
    key = _room_key(room_id)
    room_data = await r.hgetall(key)  # ty: ignore[invalid-await]
    if not room_data:
        return None
    scores = await r.hgetall(_scores_key(room_id))  # ty: ignore[invalid-await]
    out: dict[str, object] = {
        "room_id": room_id,
        "max_rounds": int(room_data.get("max_rounds", 0)),
        "time_limit": int(room_data.get("time_limit", 90)),
        "current_round": int(room_data.get("current_round", 0)),
        "host_name": room_data.get("host_name", ""),
        "visibility": room_data.get("visibility", "public"),
        "players": {k: int(v) for k, v in scores.items()} if scores else {},
    }
    return out


async def redis_delete_room(room_id: str) -> None:
    """Remove room and its scores from Redis."""
    r = await connect_redis()
    if r is None:
        return
    key = _room_key(room_id)
    pipe = r.pipeline()
    pipe.delete(key)
    pipe.delete(_scores_key(room_id))
    pipe.srem(_active_key(), room_id)
    await pipe.execute()


async def redis_room_id_exists(room_id: str) -> bool:
    """True if room exists in Redis."""
    r = await connect_redis()
    if r is None:
        return False
    return bool(await r.exists(_room_key(room_id)))


async def redis_get_active_rooms() -> list[dict[str, object]]:
    """Return all active rooms with their players."""
    r = await connect_redis()
    if r is None:
        return []
    room_ids = await r.smembers(_active_key())  # ty: ignore[invalid-await]
    if not room_ids:
        return []
    result: list[dict[str, object]] = []
    for rid in room_ids:
        snap = await redis_fetch_room_snapshot(rid)
        if snap is not None:
            result.append(snap)
    return result


async def redis_save_player_score(room_id: str, player_name: str, score: int) -> None:
    """Persist player score in Redis."""
    r = await connect_redis()
    if r is None:
        return
    key = _scores_key(room_id)
    await r.hset(key, player_name, str(score))  # ty: ignore[invalid-await]
    await r.expire(_room_key(room_id), ROOM_TTL)
    await r.expire(key, ROOM_TTL)


async def redis_remove_player(room_id: str, player_name: str) -> None:
    """Remove a player from room scores."""
    r = await connect_redis()
    if r is None:
        return
    key = _scores_key(room_id)
    await r.hdel(key, player_name)  # ty: ignore[invalid-await]
    # If no more players, keep TTL to auto-cleanup
    remaining = await r.hlen(key)  # ty: ignore[invalid-await]
    if remaining == 0:
        await redis_delete_room(room_id)
