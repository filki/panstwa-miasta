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
    assert "site-footer" in response.text
    assert "/polityka-prywatnosci" in response.text


def test_sw_js_and_manifest_served():
    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert "serviceWorker" in sw.text or "addEventListener" in sw.text
    mf = client.get("/manifest.json")
    assert mf.status_code == 200
    assert mf.headers.get("content-type", "").startswith("application/")
    assert "Państwa" in mf.text or "panstwa" in mf.text.lower()


@pytest.mark.parametrize(
    "path,needle",
    [
        ("/polityka-prywatnosci", "Polityka prywatności"),
        ("/cookies", "localStorage"),
        ("/regulamin", "Regulamin"),
    ],
)
def test_legal_pages_and_injected_footer(path: str, needle: str):
    response = client.get(path)
    assert response.status_code == 200
    assert needle in response.text
    assert "site-footer" in response.text
    assert "/regulamin" in response.text


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
        entry = next(r for r in rooms if r["id"] == room_id)
        assert entry["visibility"] == "public"
        assert entry["visibility_label"] == "Publiczny"
    finally:
        if room_id in manager.rooms:
            del manager.rooms[room_id]


def test_api_active_rooms_hides_private_room():
    from panstwa_miasta.manager import Room

    room_id = "test_room_private"
    mock_room = Room(room_id, visibility="private")
    mock_room.host_name = "Host1"
    mock_room.connections = {"Host1": None}

    manager.rooms[room_id] = mock_room
    try:
        response = client.get("/api/active-rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert not any(r["id"] == room_id for r in rooms)
    finally:
        if room_id in manager.rooms:
            del manager.rooms[room_id]


def test_api_active_rooms_hides_finished_game():
    """Finished sessions (game_over) should not look joinable on the landing page."""
    from panstwa_miasta.manager import Room

    room_id = "test_room_game_over"
    mock_room = Room(room_id)
    mock_room.host_name = "Host1"
    mock_room.connections = {"Host1": None}
    mock_room.game_over = True

    manager.rooms[room_id] = mock_room
    try:
        response = client.get("/api/active-rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert not any(r["id"] == room_id for r in rooms)
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


def _receive_json_until(websocket, msg_type: str, limit: int = 12):
    for _ in range(limit):
        data = websocket.receive_json()
        if data.get("type") == msg_type:
            return data
    return None


def test_websocket_two_players_share_score_update():
    """Drugi gracz w tym samym pokoju — obaj dostają score_update z serwera."""
    room_id = "room_two_ws"
    with client.websocket_connect(f"/ws/{room_id}/Alice") as ws_a:
        assert _receive_json_until(ws_a, "system") is not None
        with client.websocket_connect(f"/ws/{room_id}/Bob") as ws_b:
            assert _receive_json_until(ws_b, "score_update") is not None
            assert _receive_json_until(ws_a, "score_update") is not None


def test_websocket_rejection():
    """Whitespace-only nick is rejected at path validation (close 1008)."""
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as excinfo, client.websocket_connect("/ws/room_rej/  "):
        pass
    assert excinfo.value.code == 1008


def test_get_room_invalid_id_returns_422():
    response = client.get("/room/not@valid")
    assert response.status_code == 422


def test_get_room_shell_includes_footer():
    response = client.get("/room/abcd")
    assert response.status_code == 200
    assert "site-footer" in response.text
    assert "/polityka-prywatnosci" in response.text


def test_websocket_invalid_path_returns_1008():
    """Path validation rejects invalid room_id before accept."""
    from starlette.websockets import WebSocketDisconnect

    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/ws/bad@room/Player1"),
    ):
        pass
    assert excinfo.value.code == 1008


def test_websocket_extra_keys_get_error_message():
    with client.websocket_connect("/ws/room_extra/Player1") as websocket:
        for _ in range(8):
            data = websocket.receive_json()
            if data.get("type") == "system":
                break
        websocket.send_json({"type": "chat", "text": "hi", "evil": True})
        err = None
        for _ in range(6):
            msg = websocket.receive_json()
            if msg.get("type") == "error":
                err = msg
                break
        assert err is not None
        assert err.get("message") == "Invalid message"


def test_api_share_returns_404_when_missing():
    from panstwa_miasta.share_store import clear_share_snapshots

    clear_share_snapshots()
    response = client.get("/api/share/nope12345")
    assert response.status_code == 404


def test_api_share_json_and_share_page():
    from panstwa_miasta.share_store import clear_share_snapshots, record_finished_game

    clear_share_snapshots()
    record_finished_game("share_room_1", {"Gracz1": 15, "Gracz2": 8}, "Gracz1")

    rj = client.get("/api/share/share_room_1")
    assert rj.status_code == 200
    data = rj.json()
    assert data["room_id"] == "share_room_1"
    assert data["host_name"] == "Gracz1"
    assert data["scores"]["Gracz1"] == 15

    rh = client.get("/share/share_room_1")
    assert rh.status_code == 200
    assert "og:title" in rh.text
    assert "Gracz1" in rh.text
