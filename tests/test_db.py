import os

import pytest

from panstwa_miasta import db as db_module
from panstwa_miasta.db import (
    delete_room,
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

    await delete_room("test-room")
    rooms = await get_active_rooms()
    assert len(rooms) == 0
