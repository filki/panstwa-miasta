import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from panstwa_miasta.handlers import (
    _finalize_results_phase,
    handle_answers,
    handle_chat,
    handle_dissolve_room,
    handle_kick_player,
    handle_not_ready,
    handle_ready,
    handle_restart_game,
    handle_stop,
    handle_veto_vote,
    score_update_payload,
)
from panstwa_miasta.manager import Room


@pytest.mark.asyncio
async def test_finish_round_records_share_when_game_over():
    import panstwa_miasta.share_store as ss

    ss.clear_share_snapshots()
    room = Room("rg1", max_rounds=1)
    room.current_round = 1
    room.is_playing = True
    room.scores = {"P1": 42, "P2": 10}
    room.host_name = "P1"
    room.broadcast = AsyncMock()
    room.compute_round_scores = AsyncMock(return_value={})
    room.results_phase_active = True
    timeout_mock = AsyncMock()
    await _finalize_results_phase(room, "rg1", timeout_mock)
    call_args = room.broadcast.call_args[0][0]
    payload = json.loads(call_args)
    assert payload["room_id"] == "rg1"
    assert payload["game_over"] is True
    snap = ss.get_snapshot("rg1")
    assert snap is not None
    assert snap.scores["P1"] == 42
    assert room.game_over is True


@pytest.mark.asyncio
async def test_finish_round_skips_share_when_not_game_over():
    import panstwa_miasta.share_store as ss

    ss.clear_share_snapshots()
    room = Room("rg2", max_rounds=3)
    room.current_round = 1
    room.is_playing = True
    room.scores = {"P1": 5}
    room.host_name = "P1"
    room.broadcast = AsyncMock()
    room.compute_round_scores = AsyncMock(return_value={})
    room.results_phase_active = True
    timeout_mock = AsyncMock()
    await _finalize_results_phase(room, "rg2", timeout_mock)
    first_payload = json.loads(room.broadcast.call_args_list[0][0][0])
    assert first_payload["room_id"] == "rg2"
    assert first_payload["game_over"] is False
    assert ss.get_snapshot("rg2") is None
    assert room.game_over is False


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
    room.compute_round_scores = AsyncMock(return_value={})
    room.broadcast = AsyncMock()
    room.host_name = "Host1"
    timeout_mock = AsyncMock()
    await handle_answers(room, "room1", "Player1", {"answers": {"Państwo": "Polska"}}, timeout_mock)
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


@pytest.mark.asyncio
async def test_handle_dissolve_room_iterates_snapshot_not_live_dict():
    """Closing sockets runs disconnect() in other tasks, mutating connections."""
    room = Room("room1")
    room.host_name = "Host1"
    ws_a = AsyncMock()
    ws_b = AsyncMock()
    room.connections = {"Host1": ws_a, "Guest": ws_b}
    room.broadcast = AsyncMock()
    delete_mock = AsyncMock()

    async def close_a():
        room.connections.pop("Guest", None)

    ws_a.close = AsyncMock(side_effect=close_a)
    ws_b.close = AsyncMock()

    await handle_dissolve_room(room, "room1", "Host1", delete_mock)
    ws_a.close.assert_called_once()
    ws_b.close.assert_called_once()
    delete_mock.assert_called_once_with("room1")


@pytest.mark.asyncio
async def test_handle_kick_player_denied_sends_kick_denied():
    room = Room("room1")
    room.host_name = "Host1"
    ws_guest = AsyncMock()
    room.connections = {"Host1": AsyncMock(), "Guest": ws_guest}
    manager = MagicMock()
    manager.kick_player = AsyncMock(return_value=(False, "not_host"))
    await handle_kick_player(room, "room1", "Guest", {"target": "Someone"}, manager)
    ws_guest.send_text.assert_called_once()
    payload = json.loads(ws_guest.send_text.call_args[0][0])
    assert payload["type"] == "kick_denied"
    assert "host" in payload["message"].lower()


@pytest.mark.asyncio
async def test_handle_kick_player_success_no_denied_message():
    room = Room("room1")
    room.host_name = "Host1"
    room.connections = {"Host1": AsyncMock()}
    manager = MagicMock()
    manager.kick_player = AsyncMock(return_value=(True, ""))
    await handle_kick_player(room, "room1", "Host1", {"target": "Guest"}, manager)
    manager.kick_player.assert_called_once_with("room1", "Host1", "Guest")


def test_score_update_payload_includes_ready_players():
    room = Room("room1")
    room.ready_players.add("Ada")
    payload = score_update_payload(room)
    assert payload["ready_players"] == ["Ada"]
    assert payload["type"] == "score_update"


@pytest.mark.asyncio
async def test_handle_ready_ignored_after_first_round():
    room = Room("room1")
    room.current_round = 1
    room.connections = {"Player1": MagicMock()}
    room.broadcast = AsyncMock()
    timeout_mock = AsyncMock()
    await handle_ready(room, "room1", "Player1", timeout_mock)
    assert room.is_playing is False
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_veto_vote_broadcasts_tally():
    room = Room("room1")
    room.results_phase_active = True
    room.answers_received = {"Ada": {"Rzecz": "Aparat"}, "Bob": {"Rzecz": "Buty"}}
    room.broadcast = AsyncMock()
    await handle_veto_vote(room, "Bob", {"target": "Ada", "vote": "tak"})
    room.broadcast.assert_called_once()
    payload = json.loads(room.broadcast.call_args[0][0])
    assert payload["type"] == "veto_update"
    assert payload["veto_tallies"]["Ada"]["tak"] == 1


def test_vetoed_rzecz_players_majority_tak_rejects():
    room = Room("room1")
    room.answers_received = {"Ada": {"Rzecz": "Aparat"}}
    room.veto_votes = {"Ada": {"Bob": "tak", "Cal": "nie", "Dan": "tak"}}
    assert room.vetoed_rzecz_players() == {"Ada"}


def test_vetoed_rzecz_players_no_votes_keeps_answer():
    room = Room("room1")
    room.answers_received = {"Ada": {"Rzecz": "Aparat"}}
    assert room.vetoed_rzecz_players() == set()
