from unittest.mock import AsyncMock

import pytest
from fastapi import WebSocket

from panstwa_miasta.manager import ConnectionManager, Room


@pytest.fixture
def room():
    return Room("test_room", max_rounds=3, time_limit=60)


def test_normalize_room_visibility():
    from panstwa_miasta.manager import normalize_room_visibility

    assert normalize_room_visibility("private") == "private"
    assert normalize_room_visibility("PUBLIC") == "public"
    assert normalize_room_visibility("") == "public"
    assert normalize_room_visibility("evil") == "public"


def test_room_initialization(room):
    assert room.room_id == "test_room"
    assert room.max_rounds == 3
    assert room.time_limit == 60
    assert room.visibility == "public"
    assert len(room.letter_queue) == 22  # ALPHABET size


def test_room_private_visibility():
    r = Room("x", visibility="private")
    assert r.visibility == "private"
    r2 = Room("y", visibility="bogus")
    assert r2.visibility == "public"


def test_deck_shuffle_refill(room):
    # Empty the queue
    room.letter_queue = []
    # Trigger start_round which should refill
    letter = room.start_round()
    assert letter in "ABCDEFGHIJKLMNOPRSTUWZ"
    assert len(room.letter_queue) == 21


def test_22_rounds_no_repeats(room):
    """W jednej grze (do 22 rund) każda litera dokładnie raz."""
    letters = [room.start_round() for _ in range(22)]
    assert len(letters) == 22
    assert len(set(letters)) == 22, f"Powtórki w cyklu: {letters}"
    assert set(letters) == set("ABCDEFGHIJKLMNOPRSTUWZ")


def test_restart_continues_existing_queue(room):
    """`restart_game` NIE tasuje od nowa -- ciągnie z istniejącej talii."""
    import asyncio

    letters_before = [room.start_round() for _ in range(5)]
    queue_snapshot = list(room.letter_queue)

    asyncio.run(_restart(room))
    # Po restarcie talia powinna być nietknięta (poza może state'ami gry).
    assert room.letter_queue == queue_snapshot, "restart_game nie powinien tasować"
    assert room.current_round == 0

    letters_after = [room.start_round() for _ in range(5)]
    # 5 + 5 = 10 unikalnych liter łącznie (cykl 22 jeszcze niewyczerpany).
    combined = letters_before + letters_after
    assert len(set(combined)) == 10, f"Powtórki między grami: {combined}"


async def _restart(room):
    """Helper: stubuje save_* żeby restart nie wołał DB."""
    from unittest.mock import AsyncMock

    import panstwa_miasta.manager as mod

    orig_save_room = mod.save_room
    orig_save_score = mod.save_player_score
    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()
    try:
        await room.restart_game(5, 60)
    finally:
        mod.save_room = orig_save_room
        mod.save_player_score = orig_save_score


def test_recent_letters_pushed_to_bottom_after_reshuffle(room):
    """Po wyczerpaniu talii ostatnie N liter ląduje na dnie nowego cyklu."""
    # Wyczerpujemy całą talię (22 litery).
    cycle1 = [room.start_round() for _ in range(22)]
    assert room.letter_queue == []
    last7 = cycle1[-7:]

    # Następny start_round wymusza re-shuffle.
    first_of_cycle2 = room.start_round()
    # Pierwsze 15 liter cyklu 2 (czyli `last_7` z poprzedniego cyklu odłożone na DOLE)
    # NIE powinno zawierać żadnej z `last7`.
    rest_of_cycle2 = [room.start_round() for _ in range(14)]
    fresh_part = [first_of_cycle2, *rest_of_cycle2]
    assert not (set(fresh_part) & set(last7)), (
        f"Ostatnie z cyklu 1 ({last7}) pojawiły się za wcześnie w cyklu 2: {fresh_part}"
    )


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
async def test_room_broadcast_continues_after_one_send_fails():
    room = Room("test")
    ws1 = AsyncMock(spec=WebSocket)
    ws2 = AsyncMock(spec=WebSocket)
    ws1.send_text = AsyncMock(side_effect=RuntimeError("stale socket"))
    room.connections = {"p1": ws1, "p2": ws2}

    await room.broadcast("hello")
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
async def test_manager_connect_visibility_only_on_first_join():
    """Pierwsze połączenie ustawia widoczność; kolejni gracze nie nadpisują."""
    manager = ConnectionManager()
    import panstwa_miasta.manager

    panstwa_miasta.manager.save_room = AsyncMock()
    panstwa_miasta.manager.save_player_score = AsyncMock()

    ws1 = AsyncMock(spec=WebSocket)
    await manager.connect(ws1, "r_vis", "p1", 5, 90, "private")
    assert manager.rooms["r_vis"].visibility == "private"

    ws2 = AsyncMock(spec=WebSocket)
    await manager.connect(ws2, "r_vis", "p2", 5, 90, "public")
    assert manager.rooms["r_vis"].visibility == "private"


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


@pytest.mark.asyncio
async def test_disconnect_ignores_stale_socket():
    """Reconnect: old socket's WebSocketDisconnect must not remove the new socket."""
    manager = ConnectionManager()
    room = Room("room1")
    ws_new = AsyncMock(spec=WebSocket)
    ws_old = AsyncMock(spec=WebSocket)
    room.connections = {"p1": ws_new}
    manager.rooms["room1"] = room

    assert manager.disconnect("room1", "p1", ws_old) is False
    assert room.connections["p1"] is ws_new

    assert manager.disconnect("room1", "p1", ws_new) is True
    assert "room1" not in manager.rooms


@pytest.mark.asyncio
async def test_manager_kick_player_removes_target(monkeypatch):
    import panstwa_miasta.manager as mod

    mod.remove_player = AsyncMock()
    mod.save_room = AsyncMock()

    manager = ConnectionManager()
    room = Room("room1")
    ws_h = AsyncMock()
    ws_g = AsyncMock()
    room.connections = {"Host": ws_h, "Guest": ws_g}
    room.host_name = "Host"
    room.scores = {"Host": 0, "Guest": 10}
    manager.rooms["room1"] = room

    ok, err = await manager.kick_player("room1", "Host", "Guest")
    assert ok is True
    assert err == ""
    assert "Guest" not in room.connections
    assert "Guest" not in room.scores
    ws_g.send_text.assert_called_once()
    assert "kicked" in ws_g.send_text.call_args[0][0]
    ws_g.close.assert_called_once_with(code=4401)
    mod.remove_player.assert_called_once_with("room1", "Guest")
