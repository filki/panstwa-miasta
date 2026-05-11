import pytest
from fastapi.testclient import TestClient

from panstwa_miasta.db import init_db
from panstwa_miasta.main import app, manager

client = TestClient(app)


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    yield


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert "Państwa-Miasta" in response.text


def test_api_active_rooms_with_data():
    from panstwa_miasta.manager import Room

    room_id = "test_room_123"
    mock_room = Room(room_id)
    mock_room.host_name = "Host1"
    # The endpoint only returns rooms with connections
    mock_room.connections = {"Host1": None}

    manager.rooms[room_id] = mock_room
    try:
        response = client.get("/api/active-rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert any(r["id"] == room_id for r in rooms)
    finally:
        if room_id in manager.rooms:
            del manager.rooms[room_id]


def test_websocket_join_and_message():
    with client.websocket_connect("/ws/room_ws/Player1") as websocket:
        # Initial messages (score_update, system)
        found_system = False
        for _ in range(5):
            data = websocket.receive_json()
            if data.get("type") == "system":
                found_system = True
                break
        assert found_system

        # Test chat
        websocket.send_json({"type": "chat", "text": "hello"})

        # We might get another score_update if someone else joined, but here it's just us
        # Let's wait specifically for chat
        found_chat = False
        for _ in range(3):
            data = websocket.receive_json()
            if data.get("type") == "chat" and data.get("text") == "hello":
                found_chat = True
                break
        assert found_chat


def test_websocket_rejection():
    from starlette.websockets import WebSocketDisconnect

    with (
        pytest.raises(WebSocketDisconnect),
        client.websocket_connect("/ws/room_rej/  ") as ws,
    ):
        ws.receive_json()
