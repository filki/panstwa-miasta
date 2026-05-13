"""Message handlers for the WebSocket endpoint.

Extracted from main.py to reduce cognitive complexity (SonarQube CRITICAL).
Each handler is a small, single-responsibility async function.
"""

import asyncio
import json
import time

from .logger import get_logger
from .manager import RESULTS_PHASE_SECONDS, VETO_CATEGORY, ConnectionManager, Room
from .share_store import record_finished_game

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _broadcast_json(room: Room, payload: dict) -> asyncio.Task:
    """Broadcast a JSON payload and return a Task stored to prevent GC."""
    return asyncio.ensure_future(room.broadcast(json.dumps(payload)))


def score_update_payload(room: Room) -> dict:
    return {
        "type": "score_update",
        "scores": room.scores,
        "host_name": room.host_name,
        "ready_players": sorted(room.ready_players),
    }


async def _broadcast_score_update(room: Room) -> None:
    await room.broadcast(json.dumps(score_update_payload(room)))


def _round_results_payload(
    room: Room,
    room_id: str,
    *,
    final: bool,
    round_scores: dict,
    game_over: bool,
    veto_ends_at: int | None = None,
) -> dict:
    payload: dict = {
        "type": "round_results",
        "room_id": room_id,
        "answers": room.answers_received,
        "round_scores": round_scores,
        "total_scores": dict(room.scores),
        "game_over": game_over,
        "host_name": room.host_name,
        "final": final,
        "veto_tallies": room.veto_tallies(),
    }
    if not final and veto_ends_at is not None:
        payload["veto_ends_at"] = veto_ends_at
    return payload


async def _start_next_round(room: Room, room_id: str, timeout_coro) -> None:
    letter = room.start_round()
    await room.broadcast(
        json.dumps(
            {
                "type": "round_started",
                "letter": letter,
                "sender": "System",
                "current_round": room.current_round,
                "max_rounds": room.max_rounds,
                "time_limit": room.time_limit,
            }
        )
    )
    task = asyncio.ensure_future(timeout_coro(room_id, room.current_round, room.time_limit + 2))
    room._timeout_task = task  # type: ignore[attr-defined]
    logger.info(
        "Round %s started in room %s with letter '%s' after results phase",
        room.current_round,
        room_id,
        letter,
    )


async def _finalize_results_phase(room: Room, room_id: str, timeout_coro) -> None:
    if not room.results_phase_active:
        return
    room.results_phase_active = False
    room._results_phase_task = None

    rejected = room.vetoed_rzecz_players()
    round_scores = await room.compute_round_scores(veto_rejected=rejected, persist=True)
    is_game_over = room.current_round >= room.max_rounds
    if is_game_over:
        room.game_over = True
        record_finished_game(room_id, dict(room.scores), room.host_name or "")

    await room.broadcast(
        json.dumps(
            _round_results_payload(
                room,
                room_id,
                final=True,
                round_scores=round_scores,
                game_over=is_game_over,
            )
        )
    )
    room.veto_votes = {}
    room.provisional_round_scores = {}
    logger.info("Round results finalized for room %s. game_over=%s", room_id, is_game_over)

    if is_game_over:
        return
    await _start_next_round(room, room_id, timeout_coro)


async def _results_phase_countdown(room: Room, room_id: str, timeout_coro) -> None:
    try:
        await asyncio.sleep(RESULTS_PHASE_SECONDS)
    except asyncio.CancelledError:
        return
    await _finalize_results_phase(room, room_id, timeout_coro)


async def _begin_results_phase(room: Room, room_id: str, timeout_coro) -> None:
    if room.results_phase_active:
        return
    room.cancel_results_phase()
    room.is_playing = False
    room.stop_triggered = False
    room.results_phase_active = True
    room.veto_votes = {}
    round_scores = await room.compute_round_scores(persist=False)
    room.provisional_round_scores = round_scores
    veto_ends_at = int(time.time() * 1000) + RESULTS_PHASE_SECONDS * 1000
    await room.broadcast(
        json.dumps(
            _round_results_payload(
                room,
                room_id,
                final=False,
                round_scores=round_scores,
                game_over=False,
                veto_ends_at=veto_ends_at,
            )
        )
    )
    task = asyncio.ensure_future(_results_phase_countdown(room, room_id, timeout_coro))
    room._results_phase_task = task
    logger.info("Results phase started for room %s", room_id)


async def _finish_round(room: Room, room_id: str, timeout_coro) -> None:
    """Compatibility entry: starts the 10s results phase instead of immediate finalize."""
    await _begin_results_phase(room, room_id, timeout_coro)


# ---------------------------------------------------------------------------
# Individual message handlers
# ---------------------------------------------------------------------------


async def handle_chat(room: Room, client_name: str, msg: dict) -> None:
    await room.broadcast(
        json.dumps(
            {
                "type": "chat",
                "sender": client_name,
                "text": msg["text"],
            }
        )
    )


async def handle_ready(room: Room, room_id: str, client_name: str, timeout_coro) -> None:
    if room.is_playing or room.game_over or room.results_phase_active or room.current_round != 0:
        return
    room.ready_players.add(client_name)
    await room.broadcast(
        json.dumps(
            {
                "type": "system",
                "message": f"<em>{client_name} jest gotowy! ({len(room.ready_players)}/{len(room.connections)})</em>",
            }
        )
    )
    await _broadcast_score_update(room)
    all_ready = len(room.ready_players) >= len(room.connections) and len(room.connections) > 0
    if all_ready:
        letter = room.start_round()
        await room.broadcast(
            json.dumps(
                {
                    "type": "round_started",
                    "letter": letter,
                    "sender": "System",
                    "current_round": room.current_round,
                    "max_rounds": room.max_rounds,
                    "time_limit": room.time_limit,
                }
            )
        )
        # Store task reference to prevent premature GC
        task = asyncio.ensure_future(timeout_coro(room_id, room.current_round, room.time_limit + 2))
        room._timeout_task = task  # type: ignore[attr-defined]
        logger.info(f"Round {room.current_round} started in room {room_id} with letter '{letter}'")


async def handle_not_ready(room: Room, client_name: str) -> None:
    if room.is_playing or room.results_phase_active or room.current_round != 0:
        return
    room.ready_players.discard(client_name)
    await room.broadcast(
        json.dumps(
            {
                "type": "system",
                "message": f"<em>{client_name} nie jest już gotowy. ({len(room.ready_players)}/{len(room.connections)})</em>",
            }
        )
    )
    await _broadcast_score_update(room)


async def handle_restart_game(room: Room, client_name: str, msg: dict) -> None:
    if not room.game_over or client_name != room.host_name:
        return
    await room.restart_game(msg.get("rounds", 5), msg.get("limit", 90))
    await room.broadcast(
        json.dumps(
            {
                "type": "game_restarted",
                "sender": client_name,
                "scores": room.scores,
                "host_name": room.host_name,
            }
        )
    )
    logger.info(f"Game restarted in room {room.room_id} by '{client_name}'")


async def handle_dissolve_room(room: Room, room_id: str, client_name: str, delete_room_fn) -> None:
    if client_name != room.host_name:
        return
    room.cancel_results_phase()
    await room.broadcast(
        json.dumps(
            {
                "type": "room_dissolved",
                "message": "Pokój został rozwiązany przez hosta.",
            }
        )
    )
    # Snapshot: each close() triggers WebSocketDisconnect → disconnect(), which
    # removes that client from room.connections — mutating the dict mid-iterate
    # raises RuntimeError. Close other clients before the host so we do not
    # close the requester's socket while still handling their dissolve message.
    for _name, conn in sorted(room.connections.items(), key=lambda nc: nc[0] == client_name):
        await conn.close()
    await delete_room_fn(room_id)
    logger.info(f"Room {room_id} dissolved by '{client_name}'")


async def handle_stop(room: Room, room_id: str, client_name: str, force_end_coro) -> None:
    if not room.is_playing or room.stop_triggered:
        return
    room.stop_triggered = True
    await room.broadcast(
        json.dumps(
            {
                "type": "stop_round",
                "sender": client_name,
                "time_left": 10,
            }
        )
    )
    # Store task to prevent premature GC
    task = asyncio.ensure_future(force_end_coro(room_id))
    room._force_end_task = task  # type: ignore[attr-defined]
    logger.info(f"Round stopped by '{client_name}' in room {room_id}")


async def handle_answers(
    room: Room, room_id: str, client_name: str, msg: dict, timeout_coro
) -> None:
    if not room.is_playing:
        return
    room.answers_received[client_name] = msg.get("answers", {})
    logger.info(
        f"Answers received from '{client_name}' in room {room_id} ({len(room.answers_received)}/{room.expected_answers})"
    )
    if len(room.answers_received) >= room.expected_answers:
        await _begin_results_phase(room, room_id, timeout_coro)


async def handle_veto_vote(room: Room, client_name: str, msg: dict) -> None:
    if not room.results_phase_active:
        return
    target = (msg.get("target") or "").strip()
    vote = (msg.get("vote") or "").strip().lower()
    if vote not in ("tak", "nie"):
        return
    if not target or target == client_name or target not in room.answers_received:
        return
    rzecz = room.answers_received[target].get(VETO_CATEGORY, "").strip()
    if not rzecz:
        return
    room.veto_votes.setdefault(target, {})[client_name] = vote
    await room.broadcast(
        json.dumps(
            {
                "type": "veto_update",
                "target": target,
                "veto_tallies": room.veto_tallies(),
            }
        )
    )


KICK_DENIED_MESSAGES = {
    "no_room": "Pokój nie istnieje.",
    "not_host": "Tylko host może wyrzucać graczy.",
    "bad_target": "Nie można wyrzucić tego gracza.",
    "not_found": "Ta osoba nie jest w pokoju.",
}


async def handle_kick_player(
    room: Room, room_id: str, client_name: str, msg: dict, manager: ConnectionManager
) -> None:
    target = (msg.get("target") or "").strip()
    ok, err = await manager.kick_player(room_id, client_name, target)
    if ok:
        return
    text = KICK_DENIED_MESSAGES.get(err, "Nie udało się wyrzucić gracza.")
    ws = room.connections.get(client_name)
    if ws:
        try:
            await ws.send_text(json.dumps({"type": "kick_denied", "message": text}))
        except Exception as exc:
            logger.warning("kick_denied send failed: %s", exc)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

HANDLERS = {
    "chat": handle_chat,
    "ready": handle_ready,
    "not_ready": handle_not_ready,
    "restart_game": handle_restart_game,
    "dissolve_room": handle_dissolve_room,
    "stop": handle_stop,
    "answers": handle_answers,
    "veto_vote": handle_veto_vote,
}
