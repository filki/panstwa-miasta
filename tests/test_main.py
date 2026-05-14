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
    assert "buycoffee.to/filki" in response.text
    assert "landing-anon-cta--support" in response.text
    assert "landing-anon-action-col" not in response.text


def test_sw_js_and_manifest_served():
    sw = client.get("/sw.js")
    assert sw.status_code == 200
    assert "serviceWorker" in sw.text or "addEventListener" in sw.text
    mf = client.get("/manifest.json")
    assert mf.status_code == 200
    assert mf.headers.get("content-type", "").startswith("application/")
    assert "Państwa" in mf.text or "panstwa" in mf.text.lower()


@pytest.mark.parametrize(
    "path,needle,canonical",
    [
        (
            "/polityka-prywatnosci",
            "Polityka prywatności",
            "https://panstwamiasta.com.pl/polityka-prywatnosci",
        ),
        (
            "/cookies",
            "localStorage",
            "https://panstwamiasta.com.pl/cookies",
        ),
        (
            "/regulamin",
            "Regulamin",
            "https://panstwamiasta.com.pl/regulamin",
        ),
    ],
)
def test_legal_pages_and_injected_footer(path: str, needle: str, canonical: str):
    response = client.get(path)
    assert response.status_code == 200
    assert needle in response.text
    assert "site-footer" in response.text
    assert "/regulamin" in response.text
    assert "buycoffee.to/filki" in response.text
    assert f'rel="canonical" href="{canonical}"' in response.text


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


def test_api_active_rooms_hides_last_round_results_phase():
    """After the final round stops, the room should not look joinable while results are open."""
    from panstwa_miasta.manager import Room

    room_id = "test_room_final_results"
    mock_room = Room(room_id)
    mock_room.host_name = "Julka"
    mock_room.connections = {"Julka": None}
    mock_room.max_rounds = 3
    mock_room.current_round = 3
    mock_room.results_phase_active = True
    mock_room.is_playing = False

    manager.rooms[room_id] = mock_room
    try:
        response = client.get("/api/active-rooms")
        assert response.status_code == 200
        rooms = response.json()
        assert not any(r["id"] == room_id for r in rooms)
    finally:
        if room_id in manager.rooms:
            del manager.rooms[room_id]


def test_healthz_ok():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_api_create_room_returns_opaque_id():
    response = client.post(
        "/api/rooms",
        json={"rounds": 10, "limit": 120, "visibility": "private"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["room_id"]) == 10
    assert data["room_id"].isalnum()
    assert data["max_rounds"] == 10
    assert data["time_limit"] == 120
    assert data["visibility"] == "private"


def test_api_quick_join_creates_room_when_no_lobby():
    manager.rooms.clear()
    response = client.post("/api/quick-join")
    assert response.status_code == 200
    data = response.json()
    assert data["created"] is True
    assert len(data["room_id"]) == 10
    assert data["room_id"].isalnum()
    assert data["max_rounds"] == 5
    assert data["time_limit"] == 90


def test_api_quick_join_picks_busiest_public_lobby():
    from panstwa_miasta.manager import Room

    manager.rooms.clear()
    quiet = Room("quiet", 5, 90, visibility="public")
    quiet.connections = {"a": None}
    busy = Room("busy", 7, 120, visibility="public")
    busy.connections = {"a": None, "b": None, "c": None}
    manager.rooms["quiet"] = quiet
    manager.rooms["busy"] = busy
    try:
        response = client.post("/api/quick-join")
        assert response.status_code == 200
        data = response.json()
        assert data["room_id"] == "busy"
        assert data["created"] is False
        assert data["max_rounds"] == 7
        assert data["time_limit"] == 120
    finally:
        manager.rooms.pop("quiet", None)
        manager.rooms.pop("busy", None)


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
    assert "buycoffee.to/filki" in response.text


def test_umami_snippet_absent_without_env(monkeypatch):
    monkeypatch.delenv("UMAMI_SCRIPT_URL", raising=False)
    monkeypatch.delenv("UMAMI_WEBSITE_ID", raising=False)
    response = client.get("/")
    assert response.status_code == 200
    assert "data-website-id" not in response.text


def test_umami_snippet_present_with_env(monkeypatch):
    monkeypatch.setenv("UMAMI_SCRIPT_URL", "https://cloud.umami.is/script.js")
    monkeypatch.setenv("UMAMI_WEBSITE_ID", "test-website-id")
    response = client.get("/")
    assert response.status_code == 200
    assert "https://cloud.umami.is/script.js" in response.text
    assert 'data-website-id="test-website-id"' in response.text


def test_share_page_includes_umami_when_configured(monkeypatch):
    from panstwa_miasta.share_store import clear_share_snapshots, record_finished_game

    monkeypatch.setenv("UMAMI_SCRIPT_URL", "https://cloud.umami.is/script.js")
    monkeypatch.setenv("UMAMI_WEBSITE_ID", "share-page-id")
    clear_share_snapshots()
    record_finished_game("share_umami", {"Gracz1": 3}, "Gracz1")
    response = client.get("/share/share_umami")
    assert response.status_code == 200
    assert 'data-website-id="share-page-id"' in response.text


def test_robots_txt_and_sitemap():
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap: https://panstwamiasta.com.pl/sitemap.xml" in robots.text
    assert "Disallow: /api/" in robots.text
    assert "Disallow: /room/" in robots.text
    assert "Disallow: /share/" in robots.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "application/xml" in sitemap.headers.get("content-type", "")
    assert "https://panstwamiasta.com.pl/polityka-prywatnosci" in sitemap.text
    assert "<lastmod>" in sitemap.text


def test_landing_has_seo_meta():
    response = client.get("/")
    assert response.status_code == 200
    assert 'property="og:url"' in response.text
    assert 'property="og:image"' in response.text
    assert 'name="twitter:card"' in response.text
    assert 'rel="canonical"' in response.text
    assert "https://panstwamiasta.com.pl/" in response.text
    assert "application/ld+json" in response.text


def test_room_shell_is_noindex():
    response = client.get("/room/abcd")
    assert response.status_code == 200
    assert 'name="robots" content="noindex"' in response.text


def test_share_page_is_noindex():
    response = client.get("/share/abcd")
    assert response.status_code == 404
    assert 'name="robots" content="noindex, nofollow"' in response.text


def test_websocket_invalid_path_returns_1008():
    """Path validation rejects invalid room_id before accept."""
    from starlette.websockets import WebSocketDisconnect

    with (
        pytest.raises(WebSocketDisconnect) as excinfo,
        client.websocket_connect("/ws/bad@room/Player1"),
    ):
        pass
    assert excinfo.value.code == 1008


def test_websocket_accepts_encoded_hash_in_client_name():
    with client.websocket_connect(
        "/ws/room_hash/Gracz%232137?rounds=5&limit=90&visibility=public"
    ) as websocket:
        assert _receive_json_until(websocket, "system") is not None


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
