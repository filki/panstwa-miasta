"""Tests for optional Redis backend."""

from __future__ import annotations

import pytest

from panstwa_miasta.db_redis import (
    close_redis,
    connect_redis,
    redis_configured,
    redis_delete_room,
    redis_fetch_room_snapshot,
    redis_get_active_rooms,
    redis_ping,
    redis_remove_player,
    redis_room_id_exists,
    redis_save_player_score,
    redis_save_room,
)


class _FakeRedis:
    """Mock Redis client for testing."""

    def __init__(self):
        self._data: dict[str, dict[str, str]] = {}
        self._sets: dict[str, set[str]] = {}

    def pipeline(self):
        return _FakePipeline(self)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._data.get(key, {}))

    async def hset(self, key: str, field: str, value: str) -> None:
        self._data.setdefault(key, {})[field] = value

    async def hlen(self, key: str) -> int:
        return len(self._data.get(key, {}))

    async def hdel(self, key: str, field: str) -> None:
        self._data.get(key, {}).pop(field, None)

    async def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    async def expire(self, key: str, ttl: int) -> None:
        pass  # no-op in mock

    async def smembers(self, key: str) -> set[str]:
        return set(self._sets.get(key, set()))

    async def sadd(self, key: str, member: str) -> None:
        self._sets.setdefault(key, set()).add(member)

    async def srem(self, key: str, member: str) -> None:
        self._sets.get(key, set()).discard(member)

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def aclose(self) -> None:
        pass


class _FakePipeline:
    def __init__(self, redis: _FakeRedis):
        self._redis = redis
        self._ops: list = []

    def hset(self, key: str, mapping: dict[str, str]) -> None:
        self._ops.append(("hset", key, mapping))

    def sadd(self, key: str, member: str) -> None:
        self._ops.append(("sadd", key, member))

    def expire(self, key: str, ttl: int) -> None:
        self._ops.append(("expire", key, ttl))

    def delete(self, key: str) -> None:
        self._ops.append(("delete", key))

    def srem(self, key: str, member: str) -> None:
        self._ops.append(("srem", key, member))

    async def execute(self) -> None:
        for op in self._ops:
            cmd = op[0]
            if cmd == "hset":
                self._redis._data.setdefault(op[1], {}).update(op[2])
            elif cmd == "sadd":
                self._redis._sets.setdefault(op[1], set()).add(op[2])
            elif cmd == "expire":
                pass
            elif cmd == "delete":
                self._redis._data.pop(op[1], None)
            elif cmd == "srem":
                self._redis._sets.get(op[1], set()).discard(op[2])


@pytest.fixture
def fake_redis(monkeypatch):
    """Replace connect_redis with a fake Redis instance."""
    fr = _FakeRedis()
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    async def _fake_connect():
        return fr

    monkeypatch.setattr("panstwa_miasta.db_redis.connect_redis", _fake_connect)
    monkeypatch.setattr("panstwa_miasta.db_redis.redis_configured", lambda: True)
    return fr


# ---------------------------------------------------------------------------
# Basic tests
# ---------------------------------------------------------------------------


async def test_redis_not_configured_by_default():
    """Without REDIS_URL, redis should not be configured."""
    assert not redis_configured()
    conn = await connect_redis()
    assert conn is None
    assert not await redis_ping()


async def test_redis_connect_with_url(monkeypatch):
    """With REDIS_URL set, should connect and ping successfully."""
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    assert redis_configured()
    conn = await connect_redis()
    assert conn is not None
    await close_redis()


# ---------------------------------------------------------------------------
# Room persistence tests
# ---------------------------------------------------------------------------


async def test_save_and_fetch_room(fake_redis):
    await redis_save_room("test1", 5, 90, 0, "Host1", "public")
    snap = await redis_fetch_room_snapshot("test1")
    assert snap is not None
    assert snap["room_id"] == "test1"
    assert snap["max_rounds"] == 5
    assert snap["time_limit"] == 90
    assert snap["current_round"] == 0
    assert snap["host_name"] == "Host1"
    assert snap["visibility"] == "public"
    assert snap["players"] == {}


async def test_fetch_nonexistent_room(fake_redis):
    snap = await redis_fetch_room_snapshot("nonexistent")
    assert snap is None


async def test_delete_room(fake_redis):
    await redis_save_room("delete_test", 5, 90, 0, "Host", "public")
    assert await redis_fetch_room_snapshot("delete_test") is not None
    await redis_delete_room("delete_test")
    assert await redis_fetch_room_snapshot("delete_test") is None


async def test_room_id_exists(fake_redis):
    assert not await redis_room_id_exists("exists_test")
    await redis_save_room("exists_test", 5, 90, 0, "Host", "public")
    assert await redis_room_id_exists("exists_test")
    await redis_delete_room("exists_test")
    assert not await redis_room_id_exists("exists_test")


async def test_get_active_rooms(fake_redis):
    rooms = await redis_get_active_rooms()
    assert rooms == []

    await redis_save_room("active1", 5, 90, 0, "Host1", "public")
    await redis_save_room("active2", 3, 60, 0, "Host2", "private")
    rooms = await redis_get_active_rooms()
    assert len(rooms) == 2
    ids = {r["room_id"] for r in rooms}
    assert ids == {"active1", "active2"}
    assert rooms[0]["max_rounds"] in (5, 3)


async def test_save_player_score(fake_redis):
    await redis_save_room("score_test", 5, 90, 0, "Host", "public")
    await redis_save_player_score("score_test", "Ala", 10)
    await redis_save_player_score("score_test", "Bob", 20)
    snap = await redis_fetch_room_snapshot("score_test")
    assert snap is not None
    assert snap["players"] == {"Ala": 10, "Bob": 20}


async def test_remove_player(fake_redis):
    await redis_save_room("remove_test", 5, 90, 0, "Host", "public")
    await redis_save_player_score("remove_test", "Ala", 10)
    await redis_save_player_score("remove_test", "Bob", 20)

    await redis_remove_player("remove_test", "Ala")
    snap = await redis_fetch_room_snapshot("remove_test")
    assert snap is not None
    assert "Ala" not in snap["players"]
    assert snap["players"]["Bob"] == 20


async def test_remove_last_player_deletes_room(fake_redis):
    await redis_save_room("last_test", 5, 90, 0, "Host", "public")
    await redis_save_player_score("last_test", "Ala", 10)
    await redis_remove_player("last_test", "Ala")
    assert await redis_room_id_exists("last_test") is False


async def test_redis_not_configured_returns_none(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    # Reimport module state
    from panstwa_miasta.db_redis import redis_configured as rc

    assert not rc()
    assert await connect_redis() is None
    assert not await redis_ping()
    # Functions should not crash when Redis is not configured
    assert await redis_fetch_room_snapshot("x") is None
    assert await redis_room_id_exists("x") is False
    assert await redis_get_active_rooms() == []
    await redis_save_room("x", 5, 90, 0, "h", "public")
    await redis_delete_room("x")
    await redis_save_player_score("x", "p", 10)
    await redis_remove_player("x", "p")


async def test_redis_ping_exception_returns_false(fake_redis, monkeypatch):
    """redis_ping() should return False on exception."""
    original = fake_redis.ping

    async def failing_ping():
        raise ConnectionError("connection refused")

    fake_redis.ping = failing_ping
    from panstwa_miasta.db_redis import redis_ping as rp

    assert not await rp()
    fake_redis.ping = original
