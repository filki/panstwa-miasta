from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from panstwa_miasta.manager import ConnectionManager, Room
from panstwa_miasta.validator import WikipediaValidator


@pytest.mark.asyncio
async def test_room_complex_logic():
    room = Room("test_complex", max_rounds=2, time_limit=30)
    room.broadcast = AsyncMock()

    # Test start_round
    room.start_round()
    room.current_letter = "P"  # Force letter to match our answers
    assert room.is_playing is True
    assert room.current_round == 1

    # Test calculate_scores
    room.answers_received = {
        "player1": {"Państwo": "Polska", "Miasto": "Poznań"},
        "player2": {"Państwo": "Polska", "Miasto": "Płock"},
    }
    scores = await room.calculate_scores()
    # "Państwo" is duplicate -> 5 points each
    # "Miasto" unique -> 10 points each (walidacja z lokalnej tabeli cities)
    assert scores["player1"]["details"]["Państwo"] == 5
    assert scores["player1"]["details"]["Miasto"] == 10
    assert scores["player2"]["details"]["Państwo"] == 5
    assert scores["player2"]["details"]["Miasto"] == 10

    # Test restart_game
    await room.restart_game(rounds=3, limit=60)
    assert room.max_rounds == 3
    assert room.time_limit == 60
    assert room.current_round == 0
    assert room.is_playing is False


def test_normalize_text():
    from panstwa_miasta.manager import normalize_text

    assert normalize_text("  Polska-Warszawa  ") == "polska warszawa"


@pytest.mark.asyncio
async def test_validator_comprehensive():
    validator = WikipediaValidator()
    # Test different categories with cache
    validator.cache["państwo:polska"] = True
    assert await validator.validate("polska", "państwo") is True

    # Test empty term
    assert await validator.validate("", "państwo") is False
    await validator.close()


@pytest.mark.asyncio
async def test_manager_edge_cases():
    manager = ConnectionManager()
    ws = AsyncMock()

    # Test empty name rejection
    success = await manager.connect(ws, "room1", "  ", 5, 90)
    assert success is False

    # Test duplicate name reconnection (it should replace the old connection)
    await manager.connect(ws, "room2", "Player", 5, 90)
    success2 = await manager.connect(ws, "room2", "Player", 5, 90)
    assert success2 is True

    # Test disconnect non-existent
    manager.disconnect("room_none", "player_none")  # Should not raise


@pytest.mark.asyncio
async def test_websocket_handlers_comprehensive():
    from fastapi.testclient import TestClient

    from panstwa_miasta.main import app

    client = TestClient(app)

    with client.websocket_connect("/ws/room_handlers/Player1") as ws:
        # Initial messages
        ws.receive_json()
        ws.receive_json()

        # Test all types
        for msg_type in ["ready", "not_ready"]:
            ws.send_json({"type": msg_type})

        ws.send_json({"type": "answers", "answers": {"Państwo": "Polska"}})
        ws.send_json({"type": "restart_game", "rounds": 3, "limit": 45})
        ws.send_json({"type": "dissolve_room"})


@pytest.mark.asyncio
async def test_main_global_timeout():
    from panstwa_miasta.main import global_round_timeout, manager
    from panstwa_miasta.manager import Room

    room_id = "test_global_timeout"
    mock_room = Room(room_id)
    mock_room.is_playing = True
    mock_room.current_round = 1
    mock_room.stop_triggered = False
    mock_room.broadcast = AsyncMock()

    manager.rooms[room_id] = mock_room
    try:
        with patch("asyncio.sleep", AsyncMock()):
            await global_round_timeout(room_id, 1, 0)
            assert mock_room.stop_triggered is True
    finally:
        if room_id in manager.rooms:
            del manager.rooms[room_id]


@pytest.mark.asyncio
async def test_main_lifespan():
    from fastapi.testclient import TestClient

    from panstwa_miasta.main import app

    # TestClient with 'with' block triggers startup and shutdown
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_validator_full_flow():
    validator = WikipediaValidator()

    # Mock search and claims
    mock_search_resp = MagicMock()
    mock_search_resp.json.return_value = {"search": [{"label": "Polska", "id": "Q36"}]}

    mock_claims_resp = MagicMock()
    mock_claims_resp.json.return_value = {
        "entities": {
            "Q36": {
                "claims": {
                    "P31": [
                        {"mainsnak": {"datavalue": {"value": {"id": "Q6256"}}}}
                    ]  # sovereign state
                }
            }
        }
    }

    with patch.object(validator.client, "get") as mock_get:
        mock_get.side_effect = [mock_search_resp, mock_claims_resp]

        # This will trigger _search_wikidata then _get_claims then _check_category
        result = await validator.validate("Polska", "Państwo")
        assert result is True
        assert "Państwo:polska" in validator.cache

    await validator.close()


@pytest.mark.asyncio
async def test_main_force_end_round():
    from panstwa_miasta.main import force_end_round, manager
    from panstwa_miasta.manager import Room

    room_id = "test_force_end"
    mock_room = Room(room_id)
    mock_room.is_playing = True
    mock_room.stop_triggered = True  # Required for force_end_round to proceed
    mock_room.broadcast = AsyncMock()
    mock_room.calculate_scores = AsyncMock(return_value={})

    manager.rooms[room_id] = mock_room
    try:
        with patch("asyncio.sleep", AsyncMock()):
            # Test force_end_round directly
            await force_end_round(room_id)
            assert mock_room.is_playing is False
    finally:
        if room_id in manager.rooms:
            del manager.rooms[room_id]
