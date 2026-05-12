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
    assert await mgr.connect(ws1, "room_a", "p1", 5, 90, client_ip="10.0.0.1") is True
    assert await mgr.connect(ws2, "room_b", "p2", 5, 90, client_ip="10.0.0.1") is False


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
        ok = await mgr.connect(ws, f"nr{i}", f"player{i}", 5, 90, client_ip=ip)
        assert ok is True
    ws3 = AsyncMock(spec=WebSocket)
    assert await mgr.connect(ws3, "nr_fail", "p3", 5, 90, client_ip=ip) is False


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
    assert await mgr.connect(ws1, "shared", "host", 5, 90, client_ip=ip) is True
    assert await mgr.connect(ws2, "shared", "guest", 5, 90, client_ip=ip) is True


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
