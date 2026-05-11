import pytest
import os
from panstwa_miasta.db import init_db, save_room, save_player_score, get_active_rooms, delete_room, DB_PATH

@pytest.mark.asyncio
async def test_db_lifecycle():
    # Setup: ensure clean DB
    if DB_PATH.exists():
        os.remove(DB_PATH)
    
    await init_db()
    assert DB_PATH.exists()

    # Test save_room
    await save_room("test-room", 5, 90, 1, "Host1")
    rooms = await get_active_rooms()
    assert len(rooms) == 1
    assert rooms[0]["room_id"] == "test-room"
    assert rooms[0]["host_name"] == "Host1"

    # Test save_player_score
    await save_player_score("test-room", "Player1", 10)
    rooms = await get_active_rooms()
    assert rooms[0]["players"]["Player1"] == 10

    # Test delete_room
    await delete_room("test-room")
    rooms = await get_active_rooms()
    assert len(rooms) == 0

    # Cleanup
    if DB_PATH.exists():
        os.remove(DB_PATH)
