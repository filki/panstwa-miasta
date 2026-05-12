import os

import pytest

from panstwa_miasta import db as db_module
from panstwa_miasta.db import (
    delete_room,
    fetch_room_snapshot,
    get_active_rooms,
    init_db,
    save_player_score,
    save_room,
)


@pytest.mark.asyncio
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
