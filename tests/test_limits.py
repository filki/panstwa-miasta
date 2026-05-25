"""Testy limitów WS i rate limit HTTP."""

from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient

from panstwa_miasta.limits import reset_counters_for_tests
from panstwa_miasta.main import app
from panstwa_miasta.manager import ConnectionManager


@pytest.mark.asyncio
async def test_max_rooms_rejects_new_room_when_cap_reached(monkeypatch):
    monkeypatch.setenv("PM_MAX_ROOMS", "1")
    reset_counters_for_tests()

    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    mgr = ConnectionManager()
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    ok1, _ = await mgr.connect(ws1, "room_a", "p1", client_ip="10.0.0.1")
    ok2, reason2 = await mgr.connect(ws2, "room_b", "p2", client_ip="10.0.0.1")
    assert ok1 is True
    assert ok2 is False
    assert reason2 == "max_rooms"


@pytest.mark.asyncio
async def test_ws_new_rooms_per_ip_rate_limit(monkeypatch):
    monkeypatch.setenv("PM_WS_NEW_ROOMS_PER_IP_PER_MIN", "2")
    reset_counters_for_tests()

    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    mgr = ConnectionManager()
    ip = "192.0.2.50"
    for i in range(2):
        ws = AsyncMock(spec=WebSocket)
        ok, _ = await mgr.connect(ws, f"nr{i}", f"player{i}", client_ip=ip)
        assert ok is True
    ws3 = AsyncMock(spec=WebSocket)
    ok3, reason3 = await mgr.connect(ws3, "nr_fail", "p3", client_ip=ip)
    assert ok3 is False
    assert reason3 == "rate_limited"


@pytest.mark.asyncio
async def test_same_ip_can_join_second_player_in_existing_room(monkeypatch):
    monkeypatch.setenv("PM_WS_NEW_ROOMS_PER_IP_PER_MIN", "1")
    reset_counters_for_tests()

    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    mgr = ConnectionManager()
    ip = "192.0.2.51"
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    ok1, _ = await mgr.connect(ws1, "shared", "host", client_ip=ip)
    ok2, _ = await mgr.connect(ws2, "shared", "guest", client_ip=ip)
    assert ok1 is True
    assert ok2 is True


def test_http_root_returns_429_when_over_limit(monkeypatch):
    monkeypatch.setenv("PM_RATE_HTTP_ROOT", "3")
    reset_counters_for_tests()

    with TestClient(app) as client:
        for _ in range(3):
            assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429


def test_http_active_rooms_bucket_separate_from_root(monkeypatch):
    monkeypatch.setenv("PM_RATE_HTTP_ROOT", "2")
    monkeypatch.setenv("PM_RATE_HTTP_API_ACTIVE", "5")
    reset_counters_for_tests()

    with TestClient(app) as client:
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/").status_code == 429
        assert client.get("/api/active-rooms").status_code == 200


@pytest.mark.asyncio
async def test_ws_message_rate_limit(monkeypatch):
    monkeypatch.setenv("PM_WS_MESSAGES_PER_CONN_PER_MIN", "2")
    reset_counters_for_tests()
    from panstwa_miasta.limits import check_ws_message_rate

    assert await check_ws_message_rate("room1", "Anna") is True
    assert await check_ws_message_rate("room1", "Anna") is True
    assert await check_ws_message_rate("room1", "Anna") is False
