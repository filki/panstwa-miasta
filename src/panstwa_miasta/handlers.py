"""Message handlers for the WebSocket endpoint.

Extracted from main.py to reduce cognitive complexity (SonarQube CRITICAL).
Each handler is a small, single-responsibility async function.
"""

import asyncio
import copy
import json
import time

from .appeal_tokens import issue_appeal_token
from .constants import RESULTS_PHASE_SECONDS, VETO_CATEGORY
from .db import deactivate_room, save_game_transcript, save_room
from .logger import get_logger
from .manager import ConnectionManager, Room
from .share_store import record_finished_game
from .things_lexicon import persist_accepted_things

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _broadcast_json(room: Room, payload: dict) -> asyncio.Task:
    """Broadcast a JSON payload and return a Task stored to prevent GC."""
    return asyncio.ensure_future(room.broadcast(json.dumps(payload)))


def score_update_payload(room: Room) -> dict:
    connected = sorted(room.connections.keys())
    ready = sorted(room.ready_players & room.connections.keys())
    return {
        "type": "score_update",
        "scores": room.scores,
        "host_name": room.host_name,
        "ready_players": ready,
        "connected_players": connected,
    }


async def _broadcast_score_update(room: Room) -> None:
    await room.broadcast(json.dumps(score_update_payload(room)))


def lobby_state_payload(room: Room) -> dict:
    connected = sorted(room.connections.keys())
    ready = sorted(room.ready_players & room.connections.keys())
    disconnected = sorted(room.disconnected_players.keys() - room.connections.keys())
    return {
        "type": "lobby_state",
        "ready_players": ready,
        "connected_players": connected,
        "disconnected_players": disconnected,
        "host_name": room.host_name,
        "player_count": len(connected) + len(disconnected),
        "max_players": 8,
        "config": {
            "rounds": room.max_rounds,
            "limit": room.time_limit,
            "visibility": room.visibility,
            "visibility_label": "Publiczny" if room.visibility == "public" else "Prywatny",
            "stop_mechanism": room.stop_mechanism,
            "categories": room.categories,
            "custom_categories": dict(room.custom_categories),
        },
    }


async def _broadcast_lobby_state(room: Room) -> None:
    await room.broadcast(json.dumps(lobby_state_payload(room)))


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
    if game_over:
        payload["round_history"] = copy.deepcopy(room.round_history)
    return payload


async def _send_appeal_tokens(room: Room) -> None:
    for name, ws in tuple(room.connections.items()):
        token = issue_appeal_token(room.room_id, name)
        try:
            await ws.send_text(json.dumps({"type": "appeal_token", "token": token}))
        except Exception as exc:
            logger.warning("appeal_token send failed for %r: %s", name, exc)


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
    await persist_accepted_things(room, round_scores, rejected)
    room.round_history.append(
        {
            "round": room.current_round,
            "letter": room.current_letter,
            "answers": copy.deepcopy(room.answers_received),
            "round_scores": copy.deepcopy(round_scores),
            "veto_tallies": room.veto_tallies(),
            "veto_rejected": sorted(rejected),
        }
    )
    is_game_over = room.current_round >= room.max_rounds
    if is_game_over:
        room.game_over = True
        record_finished_game(room_id, dict(room.scores), room.host_name or "")
        await deactivate_room(room_id)
        await save_game_transcript(room_id, {"rounds": copy.deepcopy(room.round_history)})

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
    room.custom_veto_votes = {}
    room.provisional_round_scores = {}
    logger.info("Round results finalized for room %s. game_over=%s", room_id, is_game_over)

    if is_game_over:
        await _send_appeal_tokens(room)
        return
    await _start_next_round(room, room_id, timeout_coro)


async def _results_phase_countdown(room: Room, room_id: str, timeout_coro) -> None:
    await asyncio.sleep(RESULTS_PHASE_SECONDS)
    await _finalize_results_phase(room, room_id, timeout_coro)


async def _begin_results_phase(room: Room, room_id: str, timeout_coro) -> None:
    if room.results_phase_active:
        return
    room.cancel_results_phase()
    room.is_playing = False
    room.stop_triggered = False
    room.stop_submit_ends_at = None
    room.round_started_at = None
    room.results_phase_active = True
    room.veto_votes = {}
    room.custom_veto_votes = {}
    room.sync_results_roster()
    round_scores = await room.compute_round_scores(persist=False)
    room.provisional_round_scores = round_scores
    veto_ends_at = int(time.time() * 1000) + RESULTS_PHASE_SECONDS * 1000
    room.results_veto_ends_at = veto_ends_at / 1000.0
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
    """Compatibility entry: starts the results review phase instead of immediate finalize."""
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
    await _broadcast_lobby_state(room)
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
    await _broadcast_lobby_state(room)


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
    # Zamknij sockety WSZYSTKICH innych graczy — hosta nie zamykamy, bo
    # wciąż jesteśmy w jego pętli _handle_ws_messages. Host poczeka na
    # WebSocketDisconnect które ASGI dostarczy po powrocie z handlera.
    for _name, conn in list(room.connections.items()):
        if _name == client_name:
            continue
        try:
            await conn.close()
        except Exception as exc:
            logger.warning("dissolve: close socket for %r failed: %s", _name, exc)
    await delete_room_fn(room_id)
    logger.info(f"Room {room_id} dissolved by '{client_name}'")


async def handle_stop(room: Room, room_id: str, client_name: str, force_end_coro) -> None:
    if not room.is_playing or room.stop_triggered:
        return
    room.mark_stop_phase_started()
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
    if not room.is_playing and not room.stop_triggered:
        return
    # ZAPISZ odpowiedzi ZANIM sprawdzisz results_phase_active —
    # inaczej gracz traci odpowiedzi jeśli faza wyników wystartowała
    # między wysłaniem przez niego formularza a dotarciem wiadomości.
    answers = msg.get("answers", {})
    if answers:
        room.answers_received[client_name] = answers
    if room.results_phase_active:
        return
    answered = len(room.answers_received)
    expected = len(room.connections)
    logger.info(f"Answers received from '{client_name}' in room {room_id} ({answered}/{expected})")
    if room.all_players_answered():
        await _begin_results_phase(room, room_id, timeout_coro)


async def handle_veto_vote(room: Room, client_name: str, msg: dict) -> None:
    if not room.results_phase_active:
        return
    target = (msg.get("target") or "").strip()
    vote = (msg.get("vote") or "").strip().lower()
    cat = (msg.get("cat") or "").strip()
    if vote not in ("tak", "nie"):
        return
    if not target or target == client_name or target not in room.answers_received:
        return

    if cat:
        # Custom category veto
        if cat not in room.custom_categories:
            return
        ans = room.answers_received[target].get(cat, "").strip()
        if not ans:
            return
        key = f"{target}::{cat}"
        room.custom_veto_votes.setdefault(key, {})[client_name] = vote
    else:
        # Regular Rzecz veto
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


async def handle_lobby_config_update(
    room: Room, room_id: str, data: dict, client_name: str
) -> None:
    """Host aktualizuje konfigurację gry w lobby przez WebSocket."""
    if room.host_name != client_name:
        await room.broadcast(
            json.dumps({"type": "error", "message": "Tylko host może zmienić ustawienia."})
        )
        return
    if room.is_playing or room.current_round > 0:
        await room.broadcast(json.dumps({"type": "error", "message": "Gra już trwa."}))
        return

    rounds = int(data.get("rounds", 5))
    limit = int(data.get("limit", 90))
    visibility = data.get("visibility", "public")
    stop_mechanism = bool(data.get("stop_mechanism", True))

    if not (1 <= rounds <= 50):
        return
    if not (10 <= limit <= 600):
        return
    if visibility not in ("public", "private"):
        return

    categories = data.get("categories")
    if categories is not None:
        if not isinstance(categories, list) or len(categories) < 1:
            return
        from .constants import GAME_CATEGORIES

        valid = [c for c in categories if c in GAME_CATEGORIES]
        if len(valid) < 1:
            return
        categories = valid
    else:
        from .constants import GAME_CATEGORIES

        categories = list(GAME_CATEGORIES)

    room.max_rounds = rounds
    room.time_limit = limit
    room.visibility = visibility
    room.stop_mechanism = stop_mechanism
    room.categories = categories

    custom_cats = data.get("custom_categories")
    if custom_cats is not None:
        if not isinstance(custom_cats, dict):
            return
        cleaned = {}
        for name, veto in custom_cats.items():
            name_clean = name.strip()
            if len(name_clean) < 2 or len(name_clean) > 20:
                continue
            cleaned[name_clean] = bool(veto)
        room.custom_categories = cleaned

    await save_room(
        room_id,
        rounds,
        limit,
        room.current_round,
        room.host_name,
        visibility,
        stop_mechanism=1 if stop_mechanism else 0,
    )

    await room.broadcast(
        json.dumps(
            {
                "type": "lobby_config_update",
                "rounds": rounds,
                "limit": limit,
                "visibility": visibility,
                "visibility_label": "Publiczny" if visibility == "public" else "Prywatny",
                "stop_mechanism": stop_mechanism,
                "categories": categories,
                "custom_categories": dict(room.custom_categories),
            }
        )
    )


async def handle_add_custom_category(
    room: Room, room_id: str, data: dict, client_name: str
) -> None:
    if room.host_name != client_name:
        return
    if room.is_playing or room.current_round > 0:
        return
    name = str(data.get("name", "")).strip()
    if len(name) < 2 or len(name) > 20:
        return
    if name in room.categories or name in room.custom_categories:
        return
    veto = bool(data.get("veto", True))
    room.custom_categories[name] = veto
    await room.broadcast(
        json.dumps(
            {
                "type": "lobby_config_update",
                "rounds": room.max_rounds,
                "limit": room.time_limit,
                "visibility": room.visibility,
                "visibility_label": "Publiczny" if room.visibility == "public" else "Prywatny",
                "stop_mechanism": room.stop_mechanism,
                "categories": room.categories,
                "custom_categories": dict(room.custom_categories),
            }
        )
    )


async def handle_remove_custom_category(
    room: Room, room_id: str, data: dict, client_name: str
) -> None:
    if room.host_name != client_name:
        return
    if room.is_playing or room.current_round > 0:
        return
    name = str(data.get("name", "")).strip()
    room.custom_categories.pop(name, None)
    await room.broadcast(
        json.dumps(
            {
                "type": "lobby_config_update",
                "rounds": room.max_rounds,
                "limit": room.time_limit,
                "visibility": room.visibility,
                "visibility_label": "Publiczny" if room.visibility == "public" else "Prywatny",
                "stop_mechanism": room.stop_mechanism,
                "categories": room.categories,
                "custom_categories": dict(room.custom_categories),
            }
        )
    )


async def handle_lobby_chat(room: Room, client_name: str, data: dict) -> None:
    """Wiadomość czatu w lobby."""
    text = str(data.get("text", "")).strip()
    if not text or len(text) > 500:
        return
    await room.broadcast(
        json.dumps(
            {
                "type": "lobby_chat",
                "from": client_name,
                "text": text,
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
    "lobby_config_update": handle_lobby_config_update,
    "add_custom_category": handle_add_custom_category,
    "remove_custom_category": handle_remove_custom_category,
    "lobby_chat_msg": handle_lobby_chat,
}
