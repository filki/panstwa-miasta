"""Comprehensive tests for room state management — disconnect, reconnect, phases."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from panstwa_miasta.manager import ConnectionManager


@pytest.fixture(autouse=True)
def _mock_limits(monkeypatch):
    import panstwa_miasta.limits as lim

    monkeypatch.setattr(lim, "check_ws_before_connect", AsyncMock(return_value=True))
    monkeypatch.setattr(lim, "record_ws_connect_ok", AsyncMock())


@pytest.fixture(autouse=True)
def _mock_db(monkeypatch):
    import panstwa_miasta.manager as mod

    monkeypatch.setattr(mod, "save_room", AsyncMock())
    monkeypatch.setattr(mod, "save_player_score", AsyncMock())
    monkeypatch.setattr(mod, "HOST_REASSIGN_GRACE_SECONDS", 10)


def _mk_ws():
    ws = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.mark.asyncio
async def test_disconnect_flags_player_as_disconnected():
    mgr = ConnectionManager()
    ws_a, ws_b = _mk_ws(), _mk_ws()
    await mgr.connect(ws_a, "r_sysmsg", "Alice")
    await mgr.connect(ws_b, "r_sysmsg", "Bob")

    mgr.disconnect("r_sysmsg", "Alice", ws_a)
    await mgr.cleanup_player_after_disconnect("r_sysmsg", "Alice")

    room = mgr.rooms["r_sysmsg"]
    assert "Alice" in room.disconnected_players
    assert "Bob" not in room.disconnected_players
    assert "Bob" in room.connections  # Bob nadal polaczony


@pytest.mark.asyncio
async def test_disconnect_removes_empty_room():
    mgr = ConnectionManager()
    ws = _mk_ws()
    await mgr.connect(ws, "r_empty", "OnlyOne")
    mgr.disconnect("r_empty", "OnlyOne", ws)
    assert "r_empty" not in mgr.rooms
    mgr.cancel_delayed_room_delete("r_empty")


@pytest.mark.asyncio
async def test_reconnect_during_lobby():
    mgr = ConnectionManager()
    ws_host, ws_guest = _mk_ws(), _mk_ws()
    await mgr.connect(ws_host, "r_lobby_reconnect", "Host")
    await mgr.connect(ws_guest, "r_lobby_reconnect", "Guest")
    room = mgr.rooms["r_lobby_reconnect"]
    assert room.host_name == "Host"

    mgr.disconnect("r_lobby_reconnect", "Guest", ws_guest)
    assert "Guest" not in room.connections

    ws_guest2 = _mk_ws()
    success, _ = await mgr.connect(ws_guest2, "r_lobby_reconnect", "Guest")
    assert success
    assert "Guest" in room.connections
    assert room.host_name == "Host"


@pytest.mark.asyncio
async def test_reconnect_during_round():
    mgr = ConnectionManager()
    ws_a, ws_b = _mk_ws(), _mk_ws()
    await mgr.connect(ws_a, "r_round_reconnect", "A")
    await mgr.connect(ws_b, "r_round_reconnect", "B")
    room = mgr.rooms["r_round_reconnect"]
    room.start_round()
    assert room.expected_answers == 2

    mgr.disconnect("r_round_reconnect", "B", ws_b)
    assert room.expected_answers == 1

    ws_b2 = _mk_ws()
    await mgr.connect(ws_b2, "r_round_reconnect", "B")
    assert room.expected_answers == 2


@pytest.mark.asyncio
async def test_disconnect_during_results_phase():
    mgr = ConnectionManager()
    ws_a, ws_b = _mk_ws(), _mk_ws()
    await mgr.connect(ws_a, "r_results_dc", "A")
    await mgr.connect(ws_b, "r_results_dc", "B")
    room = mgr.rooms["r_results_dc"]
    room.start_round()
    room.answers_received["A"] = {"Państwo": "polska"}
    room.answers_received["B"] = {"Państwo": "francja"}

    mgr.disconnect("r_results_dc", "B", ws_b)
    assert room.expected_answers == 1
    assert "B" in room.answers_received  # reconnect-safe


@pytest.mark.asyncio
async def test_host_disconnect_triggers_reassign(monkeypatch):
    import panstwa_miasta.manager as mod

    monkeypatch.setattr(mod, "HOST_REASSIGN_GRACE_SECONDS", 0.01)

    mgr = ConnectionManager()
    ws_host, ws_guest = _mk_ws(), _mk_ws()
    await mgr.connect(ws_host, "r_host_leave", "Host")
    await mgr.connect(ws_guest, "r_host_leave", "Guest")
    room = mgr.rooms["r_host_leave"]

    mgr.disconnect("r_host_leave", "Host", ws_host)
    await asyncio.sleep(0.05)
    assert room.host_name == "Guest"


@pytest.mark.asyncio
async def test_room_full_rejects_extra_players(monkeypatch):
    import panstwa_miasta.manager as mod

    monkeypatch.setattr(mod, "max_players_per_room", lambda: 3)

    mgr = ConnectionManager()
    for i in range(3):
        ws = _mk_ws()
        await mgr.connect(ws, "r_full", f"P{i}")

    ws9 = _mk_ws()
    success, reason = await mgr.connect(ws9, "r_full", "Extra")
    assert success is False
    assert reason == "room_full"


@pytest.mark.asyncio
async def test_game_in_progress_rejects_late_join():
    mgr = ConnectionManager()
    ws_host = _mk_ws()
    await mgr.connect(ws_host, "r_playing_reject", "Host")
    mgr.rooms["r_playing_reject"].start_round()

    ws_late = _mk_ws()
    success, reason = await mgr.connect(ws_late, "r_playing_reject", "Late")
    assert success is False
    assert reason == "game_in_progress"


@pytest.mark.asyncio
async def test_stale_socket_disconnect_ignored():
    mgr = ConnectionManager()
    ws_old, ws_new = _mk_ws(), _mk_ws()
    await mgr.connect(ws_new, "r_stale", "Player")

    removed = mgr.disconnect("r_stale", "Player", ws_old)
    assert removed is False
    assert "Player" in mgr.rooms["r_stale"].connections
