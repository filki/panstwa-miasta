from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket

from panstwa_miasta.manager import ConnectionManager, Room


@pytest.fixture
def room():
    return Room("test_room", max_rounds=3, time_limit=60)


def test_room_initialization(room):
    assert room.room_id == "test_room"
    assert room.max_rounds == 3
    assert room.time_limit == 60
    assert len(room.letter_queue) == 22  # ALPHABET size


def test_deck_shuffle_refill(room):
    # Empty the queue
    room.letter_queue = []
    # Trigger start_round which should refill
    letter = room.start_round()
    assert letter in "ABCDEFGHIJKLMNOPRSTUWZ"
    assert len(room.letter_queue) == 21


@pytest.mark.asyncio
async def test_room_broadcast():
    room = Room("test")
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    room.connections = {"p1": ws1, "p2": ws2}

    await room.broadcast("hello")
    ws1.send_text.assert_called_once_with("hello")
    ws2.send_text.assert_called_once_with("hello")


@pytest.mark.asyncio
async def test_manager_connect():
    manager = ConnectionManager()
    ws = AsyncMock(spec=WebSocket)

    # Mock DB functions
    import panstwa_miasta.manager

    panstwa_miasta.manager.save_room = AsyncMock()
    panstwa_miasta.manager.save_player_score = AsyncMock()

    success = await manager.connect(ws, "room1", "player1", 5, 90)
    assert success is True
    assert "room1" in manager.rooms
    assert manager.rooms["room1"].host_name == "player1"
    assert "player1" in manager.rooms["room1"].connections


@pytest.mark.asyncio
async def test_manager_disconnect():
    manager = ConnectionManager()
    room = Room("room1")
    manager.rooms["room1"] = room
    ws = AsyncMock(spec=WebSocket)
    room.connections = {"p1": ws, "p2": AsyncMock(spec=WebSocket)}
    room.host_name = "p1"

    manager.disconnect("room1", "p1")
    assert "p1" not in room.connections
    assert room.host_name == "p2"  # p2 became host

    manager.disconnect("room1", "p2")
    assert "room1" not in manager.rooms  # room deleted
