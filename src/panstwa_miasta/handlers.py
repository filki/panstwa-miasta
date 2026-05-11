"""Message handlers for the WebSocket endpoint.

Extracted from main.py to reduce cognitive complexity (SonarQube CRITICAL).
Each handler is a small, single-responsibility async function.
"""

import asyncio
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import Room

from .logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _broadcast_json(room: "Room", payload: dict) -> asyncio.Task:
    """Broadcast a JSON payload and return a Task stored to prevent GC."""
    return asyncio.ensure_future(room.broadcast(json.dumps(payload)))


async def _finish_round(room: "Room", room_id: str) -> None:
    """Calculate scores, broadcast results and mark game_over if needed."""
    room.is_playing = False
    room.stop_triggered = False
    round_scores = await room.calculate_scores()
    is_game_over = room.current_round >= room.max_rounds
    if is_game_over:
        room.game_over = True
    await room.broadcast(
        json.dumps(
            {
                "type": "round_results",
                "answers": room.answers_received,
                "round_scores": round_scores,
                "total_scores": room.scores,
                "game_over": is_game_over,
                "host_name": room.host_name,
            }
        )
    )
    logger.info(f"Round results broadcast for room {room_id}. game_over={is_game_over}")


# ---------------------------------------------------------------------------
# Individual message handlers
# ---------------------------------------------------------------------------


async def handle_chat(room: "Room", client_name: str, msg: dict) -> None:
    await room.broadcast(
        json.dumps(
            {
                "type": "chat",
                "sender": client_name,
                "text": msg["text"],
            }
        )
    )


async def handle_ready(room: "Room", room_id: str, client_name: str, timeout_coro) -> None:
    if room.is_playing or room.game_over:
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


async def handle_not_ready(room: "Room", client_name: str) -> None:
    if room.is_playing:
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


async def handle_restart_game(room: "Room", client_name: str, msg: dict) -> None:
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


async def handle_dissolve_room(
    room: "Room", room_id: str, client_name: str, delete_room_fn
) -> None:
    if client_name != room.host_name:
        return
    await room.broadcast(
        json.dumps(
            {
                "type": "room_dissolved",
                "message": "Pokój został rozwiązany przez hosta.",
            }
        )
    )
    for conn in room.connections.values():
        await conn.close()
    await delete_room_fn(room_id)
    logger.info(f"Room {room_id} dissolved by '{client_name}'")


async def handle_stop(room: "Room", room_id: str, client_name: str, force_end_coro) -> None:
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


async def handle_answers(room: "Room", room_id: str, client_name: str, msg: dict) -> None:
    if not room.is_playing:
        return
    room.answers_received[client_name] = msg.get("answers", {})
    logger.info(
        f"Answers received from '{client_name}' in room {room_id} ({len(room.answers_received)}/{room.expected_answers})"
    )
    if len(room.answers_received) >= room.expected_answers:
        await _finish_round(room, room_id)


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
}
