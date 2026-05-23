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
    room.connections = {"Ada": MagicMock(), "Bob": MagicMock()}
    room.ready_players.add("Ada")
    room.ready_players.add("Eve")
    room.scores = {"Ada": 1, "Bob": 2, "Eve": 0}
    payload = score_update_payload(room)
    assert payload["ready_players"] == ["Ada"]
    assert payload["connected_players"] == ["Ada", "Bob"]
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


def test_vetoed_rzecz_players_majority_nie_rejects():
    room = Room("room1")
    room.answers_received = {"Ada": {"Rzecz": "Aparat"}}
    room.veto_votes = {"Ada": {"Bob": "nie", "Cal": "tak", "Dan": "nie"}}
    assert room.vetoed_rzecz_players() == {"Ada"}


def test_vetoed_rzecz_players_majority_tak_keeps_answer():
    room = Room("room1")
    room.answers_received = {"Ada": {"Rzecz": "Aparat"}}
    room.veto_votes = {"Ada": {"Bob": "tak"}}
    assert room.vetoed_rzecz_players() == set()


def test_vetoed_rzecz_players_no_votes_keeps_answer():
    room = Room("room1")
    room.answers_received = {"Ada": {"Rzecz": "Aparat"}}
    assert room.vetoed_rzecz_players() == set()


# --- Tests for uncovered helpers and edge cases ---


@pytest.mark.asyncio
async def test_broadcast_json():
    """_broadcast_json serializes and broadcasts a dict payload."""
    from panstwa_miasta.handlers import _broadcast_json

    room = Room("r_bc")
    room.broadcast = AsyncMock()
    task = _broadcast_json(room, {"type": "test", "val": 1})
    assert task is not None
    room.broadcast.assert_called_once()
    payload = room.broadcast.call_args[0][0]
    assert '"type"' in payload


def test_round_results_payload_final_with_history():
    """_round_results_payload with game_over includes round_history."""
    from panstwa_miasta.handlers import _round_results_payload

    room = Room("r_rrp")
    room.answers_received = {"A": {"Państwo": "Polska"}}
    room.scores = {"A": 15}
    room.host_name = "A"
    room.round_history = [{"round": 1, "letter": "p"}]
    payload = _round_results_payload(
        room,
        "r_rrp",
        final=True,
        round_scores={"A": {"total": 15, "details": {"Państwo": 15}}},
        game_over=True,
    )
    assert payload["type"] == "round_results"
    assert payload["game_over"] is True
    assert "round_history" in payload


def test_round_results_payload_non_final_with_veto_ends():
    """_round_results_payload with veto_ends_at includes the timestamp."""
    from panstwa_miasta.handlers import _round_results_payload

    room = Room("r_rrp2")
    room.answers_received = {}
    room.scores = {}
    room.host_name = "H"
    payload = _round_results_payload(
        room,
        "r_rrp2",
        final=False,
        round_scores={},
        game_over=False,
        veto_ends_at=999000,
    )
    assert payload["veto_ends_at"] == 999000


@pytest.mark.asyncio
async def test_handle_ready_returns_only_on_first_round():
    """handle_ready guards: is_playing True → early return."""
    room = Room("r_guard")
    room.is_playing = True
    room.broadcast = AsyncMock()
    timeout_mock = AsyncMock()
    await handle_ready(room, "r_guard", "Player1", timeout_mock)
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_ready_results_phase_guard():
    """handle_ready guards: results_phase_active → early return."""
    room = Room("r_rp_guard")
    room.results_phase_active = True
    room.broadcast = AsyncMock()
    timeout_mock = AsyncMock()
    await handle_ready(room, "r_rp_guard", "Player1", timeout_mock)
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_stop_not_playing_guard():
    """handle_stop guards: not is_playing → early return."""
    room = Room("r_stop_guard")
    room.is_playing = False
    room.broadcast = AsyncMock()
    force_end_mock = AsyncMock()
    await handle_stop(room, "r_stop_guard", "P1", force_end_mock)
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_stop_already_stopped_guard():
    """handle_stop guards: already stop_triggered → early return."""
    room = Room("r_stopped")
    room.is_playing = True
    room.stop_triggered = True
    room.broadcast = AsyncMock()
    force_end_mock = AsyncMock()
    await handle_stop(room, "r_stopped", "P1", force_end_mock)
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_answers_not_playing_and_not_stop_guard():
    """handle_answers guards: not playing and not stop_triggered → early return."""
    room = Room("r_ans_guard")
    room.is_playing = False
    room.stop_triggered = False
    room.broadcast = AsyncMock()
    timeout_mock = AsyncMock()
    await handle_answers(room, "r_ans_guard", "P1", {"answers": {}}, timeout_mock)
    assert "P1" not in room.answers_received


@pytest.mark.asyncio
async def test_handle_answers_results_phase_guard():
    """handle_answers saves answers but returns early if results_phase_active."""
    room = Room("r_ans_rp")
    room.is_playing = True
    room.results_phase_active = True
    room.broadcast = AsyncMock()
    timeout_mock = AsyncMock()
    await handle_answers(room, "r_ans_rp", "P1", {"answers": {"Państwo": "Polska"}}, timeout_mock)
    assert room.answers_received["P1"] == {"Państwo": "Polska"}


@pytest.mark.asyncio
async def test_handle_veto_vote_not_active_guard():
    """handle_veto_vote guards: results_phase_active False → early return."""
    room = Room("r_veto_guard")
    room.results_phase_active = False
    room.broadcast = AsyncMock()
    await handle_veto_vote(room, "P1", {"target": "P2", "vote": "tak"})
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_veto_vote_invalid_vote_guard():
    """handle_veto_vote guards: vote not 'tak'/'nie' → early return."""
    room = Room("r_veto_bad")
    room.results_phase_active = True
    room.answers_received = {"P2": {"Rzecz": "Test"}}
    room.broadcast = AsyncMock()
    await handle_veto_vote(room, "P1", {"target": "P2", "vote": "maybe"})
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_veto_vote_self_target_guard():
    """handle_veto_vote guards: target == client_name → early return."""
    room = Room("r_veto_self")
    room.results_phase_active = True
    room.answers_received = {"P1": {"Rzecz": "Test"}}
    room.broadcast = AsyncMock()
    await handle_veto_vote(room, "P1", {"target": "P1", "vote": "nie"})
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_dissolve_room_non_host_guard():
    """handle_dissolve_room guards: not host → early return."""
    room = Room("r_diss")
    room.host_name = "Host"
    room.broadcast = AsyncMock()
    delete_mock = AsyncMock()
    await handle_dissolve_room(room, "r_diss", "NotHost", delete_mock)
    room.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_restart_game_non_host_guard():
    """handle_restart_game guards: not host → early return."""
    room = Room("r_rest")
    room.host_name = "Host"
    room.game_over = True
    room.restart_game = AsyncMock()
    room.broadcast = AsyncMock()
    await handle_restart_game(room, "NotHost", {"rounds": 5})
    room.restart_game.assert_not_called()


@pytest.mark.asyncio
async def test_handle_restart_game_not_game_over_guard():
    """handle_restart_game guards: not game_over → early return."""
    room = Room("r_rest2")
    room.host_name = "Host"
    room.game_over = False
    room.restart_game = AsyncMock()
    room.broadcast = AsyncMock()
    await handle_restart_game(room, "Host", {"rounds": 5})
    room.restart_game.assert_not_called()


@pytest.mark.asyncio
async def test_handle_not_ready_playing_guard():
    """handle_not_ready guards: is_playing True → early return."""
    room = Room("r_nr")
    room.is_playing = True
    room.broadcast = AsyncMock()
    await handle_not_ready(room, "P1")
    room.broadcast.assert_not_called()
