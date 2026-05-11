import pytest
from unittest.mock import AsyncMock, MagicMock
from panstwa_miasta.handlers import (
    handle_chat, handle_ready, handle_not_ready, 
    handle_restart_game, handle_dissolve_room, 
    handle_stop, handle_answers
)
from panstwa_miasta.manager import Room

@pytest.mark.asyncio
async def test_handle_chat():
    room = Room("room1")
    room.broadcast = AsyncMock()
    await handle_chat(room, "Player1", {"text": "hello"})
    room.broadcast.assert_called_once()

@pytest.mark.asyncio
async def test_handle_ready():
    room = Room("room1")
    room.connections = {"Player1": MagicMock()}
    room.broadcast = AsyncMock()
    
    timeout_mock = AsyncMock()
    await handle_ready(room, "room1", "Player1", timeout_mock)
    
    # Since Player1 is the only connection, all_ready is True
    # handle_ready calls room.start_round() which sets is_playing=True and clears ready_players
    assert room.is_playing is True
    room.broadcast.assert_called()

@pytest.mark.asyncio
async def test_handle_stop():
    room = Room("room1")
    room.is_playing = True
    room.broadcast = AsyncMock()
    
    force_end_mock = AsyncMock()
    await handle_stop(room, "room1", "Player1", force_end_mock)
    
    assert room.stop_triggered is True
    room.broadcast.assert_called()

@pytest.mark.asyncio
async def test_handle_answers():
    room = Room("room1")
    room.is_playing = True
    room.expected_answers = 1
    room.calculate_scores = AsyncMock(return_value={})
    room.broadcast = AsyncMock()
    room.host_name = "Host1"
    await handle_answers(room, "room1", "Player1", {"answers": {"Państwo": "Polska"}})
    assert room.answers_received["Player1"]["Państwo"] == "Polska"

@pytest.mark.asyncio
async def test_handle_not_ready():
    room = Room("room1")
    room.ready_players.add("Player1")
    room.broadcast = AsyncMock()
    await handle_not_ready(room, "Player1")
    assert "Player1" not in room.ready_players
    room.broadcast.assert_called()

@pytest.mark.asyncio
async def test_handle_restart_game():
    room = Room("room1")
    room.host_name = "Host1"
    room.game_over = True
    room.restart_game = AsyncMock()
    room.broadcast = AsyncMock()
    await handle_restart_game(room, "Host1", {"rounds": 5, "limit": 90})
    room.restart_game.assert_called_once()

@pytest.mark.asyncio
async def test_handle_dissolve_room():
    room = Room("room1")
    room.host_name = "Host1"
    room.broadcast = AsyncMock()
    delete_mock = AsyncMock()
    await handle_dissolve_room(room, "room1", "Host1", delete_mock)
    room.broadcast.assert_called()
    delete_mock.assert_called_once_with("room1")

