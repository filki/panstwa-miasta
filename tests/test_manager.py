import asyncio
from unittest.mock import AsyncMock, MagicMock

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
    manager.cancel_delayed_room_delete("room1")


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
    manager.cancel_delayed_room_delete("room1")


@pytest.mark.asyncio
async def test_connect_resyncs_expected_answers_mid_round_reconnect(monkeypatch):
    """Po disconnect w rundzie `expected_answers` maleje; reconnect ustawia z powrotem na N graczy."""
    import panstwa_miasta.manager as mod

    monkeypatch.setattr(mod, "save_room", AsyncMock())
    monkeypatch.setattr(mod, "save_player_score", AsyncMock())

    manager = ConnectionManager()
    ws_a = AsyncMock(spec=WebSocket)
    ws_b = AsyncMock(spec=WebSocket)
    await manager.connect(ws_a, "rx_exp", "A", 3, 60)
    await manager.connect(ws_b, "rx_exp", "B", 3, 60)
    room = manager.rooms["rx_exp"]
    room.start_round()
    assert room.expected_answers == 2

    manager.disconnect("rx_exp", "B", ws_b)
    assert room.expected_answers == 1

    ws_b2 = AsyncMock(spec=WebSocket)
    await manager.connect(ws_b2, "rx_exp", "B", 3, 60)
    assert room.expected_answers == 2


@pytest.mark.asyncio
async def test_reconnect_mid_round_clears_stale_answers(monkeypatch):
    """Reconnect w rundzie: stary wpis w answers_received nie blokuje zakończenia rundy."""
    import panstwa_miasta.manager as mod

    monkeypatch.setattr(mod, "save_room", AsyncMock())
    monkeypatch.setattr(mod, "save_player_score", AsyncMock())

    manager = ConnectionManager()
    ws_a = AsyncMock(spec=WebSocket)
    ws_b = AsyncMock(spec=WebSocket)
    await manager.connect(ws_a, "rx_ans", "A", 3, 60)
    await manager.connect(ws_b, "rx_ans", "B", 3, 60)
    room = manager.rooms["rx_ans"]
    room.start_round()
    room.answers_received["B"] = {"Państwo": "polska"}

    manager.disconnect("rx_ans", "B", ws_b)
    assert "B" not in room.answers_received

    ws_b2 = AsyncMock(spec=WebSocket)
    await manager.connect(ws_b2, "rx_ans", "B", 3, 60)
    assert "B" not in room.answers_received
    assert room.expected_answers == 2


@pytest.mark.asyncio
async def test_connect_restores_room_snapshot_from_sqlite(monkeypatch):
    """Gdy RAM jest pusty, ale w SQLite jest pokój — `connect` odtwarza Room ze scores."""
    import panstwa_miasta.manager as mod
    from panstwa_miasta import db as dbmod

    rid = "hroom_snap"
    await dbmod.save_room(rid, 9, 120, 3, "A", "private")
    await dbmod.save_player_score(rid, "A", 15)
    await dbmod.save_player_score(rid, "B", 7)

    monkeypatch.setattr(mod, "save_room", AsyncMock())
    monkeypatch.setattr(mod, "save_player_score", AsyncMock())

    manager = ConnectionManager()
    ws = AsyncMock(spec=WebSocket)
    ok = await manager.connect(ws, rid, "A", 5, 90, "public")
    assert ok is True
    room = manager.rooms[rid]
    assert room.max_rounds == 9
    assert room.time_limit == 120
    assert room.current_round == 3
    assert room.visibility == "private"
    assert room.scores["A"] == 15
    assert room.scores["B"] == 7

    manager.cancel_delayed_room_delete(rid)
    await dbmod.delete_room(rid)


@pytest.mark.asyncio
async def test_delayed_delete_removes_room_from_sqlite(monkeypatch):
    """Po opuszczeniu przez ostatniego gracza rekord w DB znika po grace (skróconym w teście)."""
    import panstwa_miasta.manager as mod
    from panstwa_miasta import db as dbmod

    monkeypatch.setattr(dbmod, "ROOM_EMPTY_GRACE_SECONDS", 0.05)
    monkeypatch.setattr(mod, "save_room", dbmod.save_room)
    monkeypatch.setattr(mod, "save_player_score", dbmod.save_player_score)

    manager = ConnectionManager()
    ws = AsyncMock(spec=WebSocket)
    rid = "droom_grace"
    await manager.connect(ws, rid, "solo", 3, 60)

    manager.disconnect(rid, "solo", ws)
    assert rid not in manager.rooms
    assert await dbmod.fetch_room_snapshot(rid) is not None

    await asyncio.sleep(0.2)
    assert await dbmod.fetch_room_snapshot(rid) is None
    manager.cancel_delayed_room_delete(rid)


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


@pytest.mark.asyncio
async def test_calculate_scores_zwierze_roslina_local():
    """Zwierzę / Roślina z lokalnych zbiorów (bez HTTP)."""
    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    room = Room("room_fauna", max_rounds=1, time_limit=30)
    room.start_round()
    room.current_letter = "L"
    room.answers_received = {"solo": {"Zwierzę": "labraks", "Roślina": "lipa"}}
    scores = await room.calculate_scores()
    assert scores["solo"]["details"]["Zwierzę"] == 15
    assert scores["solo"]["details"]["Roślina"] == 15


@pytest.mark.asyncio
async def test_calculate_scores_zwierze_first_word_prefix():
    """Ogólna nazwa rodzaju (np. „dzięcioł”) zalicza się, gdy w seedzie są gatunki „dzięcioł …”."""
    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    room = Room("room_woodpecker", max_rounds=1, time_limit=30)
    room.start_round()
    room.current_letter = "D"
    room.answers_received = {"solo": {"Zwierzę": "dzięcioł"}}
    scores = await room.calculate_scores()
    assert scores["solo"]["details"]["Zwierzę"] == 15


@pytest.mark.asyncio
async def test_calculate_scores_roslina_first_word_prefix():
    """To samo dla flory: „bez” → wpisy „bez czarny” itd."""
    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    room = Room("room_elder", max_rounds=1, time_limit=30)
    room.start_round()
    room.current_letter = "B"
    room.answers_received = {"solo": {"Roślina": "bez"}}
    scores = await room.calculate_scores()
    assert scores["solo"]["details"]["Roślina"] == 15


@pytest.mark.asyncio
async def test_calculate_scores_zwierze_prefix_too_short_rejected():
    """Prefiks < 3 znaków nie włącza dopasowania „pierwsze słowo + reszta”."""
    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    room = Room("room_short", max_rounds=1, time_limit=30)
    room.start_round()
    room.current_letter = "L"
    room.answers_received = {"solo": {"Zwierzę": "la"}}
    scores = await room.calculate_scores()
    assert scores["solo"]["details"]["Zwierzę"] == 0


@pytest.mark.asyncio
async def test_calculate_scores_miasto_uran_blocklisted():
    """„uran” nie jest akceptowane jako Miasto (GeoNames: Uran, Indie vs pierwiastek)."""
    import panstwa_miasta.manager as mod
    from panstwa_miasta import data

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    room = Room("room_uran_city", max_rounds=1, time_limit=30)
    room.start_round()
    room.current_letter = "u"
    room.answers_received = {"solo": {"Miasto": "uran"}}
    scores = await room.calculate_scores()
    assert scores["solo"]["details"]["Miasto"] == 0
    assert "uran" not in data.MIASTA


def test_answer_first_letter_matches_polish_diacritics():
    """Runda losuje ASCII; odpowiedź może zaczynać się od Ś, Ć, Ź, Ż, Ł, …"""
    from panstwa_miasta.manager import _answer_first_letter_matches_round

    assert _answer_first_letter_matches_round("świerk", "S")
    assert _answer_first_letter_matches_round("Świerk", "S")
    assert _answer_first_letter_matches_round("źrebak", "Z")
    assert _answer_first_letter_matches_round("żrebak", "Z")
    assert _answer_first_letter_matches_round("ćma", "C")
    assert _answer_first_letter_matches_round("łódź", "L")


@pytest.mark.asyncio
async def test_calculate_scores_zwierze_zrebak_letter_z():
    """Litera Z + potoczne „źrebak” / „zrebak” (EXTRA + alias ASCII)."""
    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    room = Room("room_foal", max_rounds=1, time_limit=30)
    room.start_round()
    room.current_letter = "Z"
    room.answers_received = {"solo": {"Zwierzę": "źrebak"}}
    scores = await room.calculate_scores()
    assert scores["solo"]["details"]["Zwierzę"] == 15

    room2 = Room("room_foal2", max_rounds=1, time_limit=30)
    room2.start_round()
    room2.current_letter = "Z"
    room2.answers_received = {"solo": {"Zwierzę": "zrebak"}}
    scores2 = await room2.calculate_scores()
    assert scores2["solo"]["details"]["Zwierzę"] == 15


@pytest.mark.asyncio
async def test_compute_round_scores_includes_connected_players_without_answers():
    import panstwa_miasta.manager as mod

    mod.save_room = AsyncMock()
    mod.save_player_score = AsyncMock()

    room = Room("room_roster", max_rounds=1, time_limit=30)
    room.start_round()
    room.current_letter = "u"
    room.connections = {"Ada": MagicMock(), "Bob": MagicMock()}
    room.answers_received = {
        "Ada": {
            "Państwo": "Ukraina",
            "Miasto": "",
            "Rzecz": "ukulele",
            "Zwierzę": "",
            "Roślina": "",
            "Imię": "",
            "Zawód": "",
        }
    }

    scores = await room.compute_round_scores(persist=False)

    assert set(scores) == {"Ada", "Bob"}
    assert scores["Bob"]["total"] == 0
