import os
from unittest.mock import AsyncMock

import pytest

from panstwa_miasta import db as db_module
from panstwa_miasta.db import (
    deactivate_room,
    delete_room,
    fetch_room_snapshot,
    get_active_rooms,
    init_db,
    remove_player,
    room_id_exists,
    save_player_score,
    save_room,
)

# ---------------------------------------------------------------------------
# Dispatch tests — Redis mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis_dispatch(monkeypatch):
    """Mock redis_configured to return True and mock the redis_* functions."""
    monkeypatch.setattr("panstwa_miasta.db.redis_configured", lambda: True)
    for fn in [
        "redis_save_room",
        "redis_save_player_score",
        "redis_delete_room",
        "redis_fetch_room_snapshot",
        "redis_room_id_exists",
        "redis_remove_player",
        "redis_get_active_rooms",
    ]:
        monkeypatch.setattr(f"panstwa_miasta.db.{fn}", AsyncMock(return_value=None))
    return monkeypatch


async def test_save_room_dispatches_to_redis(mock_redis_dispatch):
    await save_room("test", 5, 90, 0, "host")
    from panstwa_miasta.db import redis_save_room

    redis_save_room.assert_awaited_once_with("test", 5, 90, 0, "host", "public")


async def test_save_player_score_dispatches_to_redis(mock_redis_dispatch):
    await save_player_score("test", "player", 10)
    from panstwa_miasta.db import redis_save_player_score

    redis_save_player_score.assert_awaited_once_with("test", "player", 10)


async def test_delete_room_dispatches_to_redis(mock_redis_dispatch):
    await delete_room("test")
    from panstwa_miasta.db import redis_delete_room

    redis_delete_room.assert_awaited_once_with("test")


async def test_fetch_room_snapshot_dispatches_to_redis(mock_redis_dispatch):
    mock_redis_dispatch.setattr(
        "panstwa_miasta.db.redis_fetch_room_snapshot",
        AsyncMock(return_value={"room_id": "test"}),
    )
    result = await fetch_room_snapshot("test")
    from panstwa_miasta.db import redis_fetch_room_snapshot

    redis_fetch_room_snapshot.assert_awaited_once_with("test")
    assert result == {"room_id": "test"}


async def test_room_id_exists_dispatches_to_redis(mock_redis_dispatch):
    mock_redis_dispatch.setattr(
        "panstwa_miasta.db.redis_room_id_exists",
        AsyncMock(return_value=True),
    )
    assert await room_id_exists("test") is True
    from panstwa_miasta.db import redis_room_id_exists

    redis_room_id_exists.assert_awaited_once_with("test")


async def test_remove_player_dispatches_to_redis(mock_redis_dispatch):
    await remove_player("test", "player")
    from panstwa_miasta.db import redis_remove_player

    redis_remove_player.assert_awaited_once_with("test", "player")


async def test_get_active_rooms_dispatches_to_redis(mock_redis_dispatch):
    mock_redis_dispatch.setattr(
        "panstwa_miasta.db.redis_get_active_rooms",
        AsyncMock(return_value=[{"room_id": "test"}]),
    )
    result = await get_active_rooms()
    from panstwa_miasta.db import redis_get_active_rooms

    redis_get_active_rooms.assert_awaited_once()
    assert result == [{"room_id": "test"}]


async def test_deactivate_room_noop_when_redis(mock_redis_dispatch):
    """When Redis configured, deactivate_room does nothing."""
    await deactivate_room("test")
    # Just check it doesn't crash — no assertion needed, redis ops not called


async def test_db_lifecycle():
    if db_module.DB_PATH.exists():
        os.remove(db_module.DB_PATH)

    await init_db()
    assert db_module.DB_PATH.exists()

    await save_room("test-room", 5, 90, 1, "Host1")
    rooms = await get_active_rooms()
    assert len(rooms) == 1
    assert rooms[0]["room_id"] == "test-room"
    assert rooms[0]["host_name"] == "Host1"

    await save_player_score("test-room", "Player1", 10)
    rooms = await get_active_rooms()
    assert rooms[0]["players"]["Player1"] == 10

    from panstwa_miasta.db import remove_player

    await remove_player("test-room", "Player1")
    rooms = await get_active_rooms()
    assert "Player1" not in rooms[0]["players"]

    await delete_room("test-room")
    rooms = await get_active_rooms()
    assert len(rooms) == 0


@pytest.mark.asyncio
async def test_fetch_room_snapshot_returns_players_map():
    rid = "snap-room-88"
    await save_room(rid, 7, 45, 2, "HostX", "public")
    await save_player_score(rid, "Alice", 5)
    await save_player_score(rid, "Bob", 12)
    snap = await fetch_room_snapshot(rid)
    assert snap is not None
    assert snap["room_id"] == rid
    assert snap["max_rounds"] == 7
    assert snap["time_limit"] == 45
    assert snap["current_round"] == 2
    assert snap["host_name"] == "HostX"
    assert snap["players"] == {"Alice": 5, "Bob": 12}
    await delete_room(rid)
    assert await fetch_room_snapshot(rid) is None
