import asyncio
import json
import pathlib
from contextlib import asynccontextmanager

import aiofiles
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .data import reload_countries, reload_names
from .db import delete_room, init_db
from .handlers import (
    handle_answers,
    handle_chat,
    handle_dissolve_room,
    handle_not_ready,
    handle_ready,
    handle_restart_game,
    handle_stop,
)
from .logger import get_logger
from .manager import ConnectionManager

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup: initializing DB and loading rooms")
    await init_db()
    await reload_countries()
    await reload_names()
    await manager.load_from_db()
    logger.info("Startup completed")
    yield
    logger.info("Application shutdown")


app = FastAPI(title="Państwa-Miasta Engine", lifespan=lifespan)
manager = ConnectionManager()

# Montowanie plików statycznych
static_path = pathlib.Path(__file__).parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

INDEX_PATH = pathlib.Path(__file__).parent.parent.parent / "static" / "index.html"
ROOM_PATH = pathlib.Path(__file__).parent.parent.parent / "static" / "room.html"
SW_PATH = pathlib.Path(__file__).parent.parent.parent / "static" / "sw.js"
MANIFEST_PATH = pathlib.Path(__file__).parent.parent.parent / "static" / "manifest.json"


# ---------------------------------------------------------------------------
# Round timeout helpers
# ---------------------------------------------------------------------------


async def global_round_timeout(room_id: str, round_num: int, wait_time: int) -> None:
    """Fires a stop_round event when time runs out."""
    await asyncio.sleep(wait_time)
    if room_id not in manager.rooms:
        return
    room = manager.rooms[room_id]
    if room.is_playing and room.current_round == round_num and not room.stop_triggered:
        room.stop_triggered = True
        await room.broadcast(
            json.dumps(
                {
                    "type": "stop_round",
                    "sender": "System (Koniec czasu)",
                    "time_left": 10,
                }
            )
        )
        # Store task reference to prevent premature GC (SonarQube MAJOR)
        task = asyncio.ensure_future(force_end_round(room_id))
        room._global_timeout_task = task
        logger.info(f"Global timeout fired for room {room_id}, round {round_num}")


async def force_end_round(room_id: str) -> None:
    """Forces round results after the 10-second countdown."""
    await asyncio.sleep(12)
    if room_id not in manager.rooms:
        return
    room = manager.rooms[room_id]
    if not (room.is_playing and room.stop_triggered):
        return
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
    logger.info(f"Force-ended round for room {room_id}. game_over={is_game_over}")


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


@app.get("/")
async def get_root() -> HTMLResponse:
    # Use async file read (SonarQube MAJOR: avoid sync open in async function)
    async with aiofiles.open(INDEX_PATH, encoding="utf-8") as f:
        html_content = await f.read()
    return HTMLResponse(content=html_content)


@app.get("/room/{room_id}")
async def get_room(room_id: str) -> HTMLResponse:
    # Use separate room page instead of rendering landing page.
    async with aiofiles.open(ROOM_PATH, encoding="utf-8") as f:
        html_content = await f.read()
    return HTMLResponse(content=html_content)


# Service worker must be served from a top-level scope to control all routes.
@app.get("/sw.js")
async def get_service_worker() -> FileResponse:
    return FileResponse(SW_PATH, media_type="application/javascript")


@app.get("/manifest.json")
async def get_manifest() -> FileResponse:
    return FileResponse(MANIFEST_PATH, media_type="application/manifest+json")


@app.get("/api/active-rooms")
async def get_active_rooms():
    return [
        {
            "id": r_id,
            "players": len(room.connections),
            "host": room.host_name or "Anonim",
            "current_round": room.current_round,
            "max_rounds": room.max_rounds,
            "time_limit": room.time_limit,
            "mode": "Standard",  # Na razie wszystkie standardowe
        }
        for r_id, room in manager.rooms.items()
        if room.connections
    ]


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


async def _send_initial_state(websocket: WebSocket, room, client_name: str) -> None:
    """Broadcast join messages and resume state if a round is in progress."""
    await room.broadcast(
        json.dumps({"type": "system", "message": f"{client_name} dołączył do gry"})
    )
    await room.broadcast(
        json.dumps({"type": "score_update", "scores": room.scores, "host_name": room.host_name})
    )

    if room.is_playing:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "round_started",
                    "letter": room.current_letter,
                    "sender": "Serwer (Wznowienie)",
                    "current_round": room.current_round,
                    "max_rounds": room.max_rounds,
                    "time_limit": room.time_limit,
                }
            )
        )
    elif room.game_over:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "round_results",
                    "answers": {},
                    "round_scores": {},
                    "total_scores": room.scores,
                    "game_over": True,
                    "host_name": room.host_name,
                }
            )
        )


async def _dispatch(msg: dict, room, room_id: str, client_name: str) -> None:
    """Route a message to the appropriate handler."""
    msg_type = msg.get("type")
    logger.info(f"Message '{msg_type}' from '{client_name}' in room {room_id}")

    if msg_type == "chat":
        await handle_chat(room, client_name, msg)
    elif msg_type == "ready":
        await handle_ready(room, room_id, client_name, global_round_timeout)
    elif msg_type == "not_ready":
        await handle_not_ready(room, client_name)
    elif msg_type == "restart_game":
        await handle_restart_game(room, client_name, msg)
    elif msg_type == "dissolve_room":
        await handle_dissolve_room(room, room_id, client_name, delete_room)
    elif msg_type == "stop":
        await handle_stop(room, room_id, client_name, force_end_round)
    elif msg_type == "answers":
        await handle_answers(room, room_id, client_name, msg)
    else:
        logger.warning(f"Unknown message type '{msg_type}' from '{client_name}'")


@app.websocket("/ws/{room_id}/{client_name}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    client_name: str,
    rounds: int = 5,
    limit: int = 90,
) -> None:
    logger.info(
        f"WebSocket attempt: room={room_id}, client={client_name}, rounds={rounds}, limit={limit}"
    )
    success = await manager.connect(websocket, room_id, client_name, rounds, limit)
    if not success:
        logger.warning(f"Connection rejected for {client_name} in room {room_id}")
        await websocket.close(code=1008)
        return

    room = manager.rooms[room_id]
    await _send_initial_state(websocket, room, client_name)

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Raw data from '{client_name}': {data}")
            try:
                msg = json.loads(data)
                await _dispatch(msg, room, room_id, client_name)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from '{client_name}': {data}")
            except Exception as exc:
                logger.exception(f"Error handling message from '{client_name}': {exc}")
    except WebSocketDisconnect:
        logger.info(f"WebSocketDisconnect: '{client_name}' left room {room_id}")
        manager.disconnect(room_id, client_name)
        if room_id in manager.rooms:
            room = manager.rooms[room_id]
            await room.broadcast(
                json.dumps({"type": "system", "message": f"{client_name} opuścił grę"})
            )
            await room.broadcast(
                json.dumps(
                    {"type": "score_update", "scores": room.scores, "host_name": room.host_name}
                )
            )
            logger.info(f"Notified room {room_id} about departure of '{client_name}'")
