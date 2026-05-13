import asyncio
import json
import pathlib
from contextlib import asynccontextmanager, suppress
from html import escape
from typing import Annotated, Literal, cast

import aiofiles
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .api_models import (
    ActiveRoomRow,
    AppealIn,
    AppealOut,
    ClientNamePath,
    QuickJoinOut,
    RoomIdPath,
    ShareSnapshotOut,
)
from .appeals_service import submit_appeal
from .data import (
    reload_countries,
    reload_jobs,
    reload_miasta,
    reload_names,
    reload_rosliny,
    reload_zwierzeta,
)
from .db import delete_room, fetch_game_transcript, init_db
from .handlers import (
    _begin_results_phase,
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
from .limits import (
    check_http_rate_limit,
    client_ip_from_request,
    client_ip_from_websocket,
    http_rate_bucket_name,
)
from .logger import get_logger
from .manager import (
    RESULTS_PHASE_SECONDS,
    STOP_SUBMIT_GRACE_SECONDS,
    ConnectionManager,
    room_listed_in_active_lobby,
)
from .ws_messages import ws_inbound_adapter

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup: initializing DB and loading rooms")
    await init_db()
    await reload_countries()
    await reload_miasta()
    await reload_names()
    await reload_jobs()
    await reload_zwierzeta()
    await reload_rosliny()
    await manager.load_from_db()
    logger.info("Startup completed")
    yield
    logger.info("Application shutdown")


app = FastAPI(title="Państwa-Miasta Engine", lifespan=lifespan)
manager = ConnectionManager()


async def delete_room_immediate(room_id: str) -> None:
    """Rozwiązanie pokoju przez hosta: anuluj grace-delete i skasuj z SQLite."""
    manager.cancel_delayed_room_delete(room_id)
    await delete_room(room_id)


@app.middleware("http")
async def rate_limit_http_middleware(request: Request, call_next):
    bucket = http_rate_bucket_name(request.url.path)
    if bucket is not None and (
        request.method in ("GET", "HEAD")
        or request.url.path.startswith("/api/quick-join")
        or request.url.path.endswith("/appeals")
    ):
        ip = client_ip_from_request(request)
        blocked = await check_http_rate_limit(ip, bucket)
        if blocked is not None:
            return blocked
    return await call_next(request)


# Montowanie plików statycznych
static_path = pathlib.Path(__file__).parent.parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_path), name="static")

INDEX_PATH = static_path / "index.html"
ROOM_PATH = static_path / "room.html"
SW_PATH = static_path / "sw.js"
MANIFEST_PATH = static_path / "manifest.json"
POLITYKA_PATH = static_path / "polityka-prywatnosci.html"
COOKIES_LEGAL_PATH = static_path / "cookies.html"
REGULAMIN_PATH = static_path / "regulamin.html"
FOOTER_PARTIAL_PATH = static_path / "partials" / "site-footer.html"
FOOTER_HTML = FOOTER_PARTIAL_PATH.read_text(encoding="utf-8")


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
    """Forces round results after the post-stop submit window."""
    await asyncio.sleep(RESULTS_PHASE_SECONDS + STOP_SUBMIT_GRACE_SECONDS)
    if room_id not in manager.rooms:
        return
    room = manager.rooms[room_id]
    if not (room.is_playing and room.stop_triggered):
        return
    await _begin_results_phase(room, room_id, global_round_timeout)
    logger.info("Force-ended round for room %s via results phase", room_id)


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------


async def _html_with_injected_footer(page_path: pathlib.Path) -> HTMLResponse:
    """Serves HTML and replaces ``<!-- SITE_FOOTER -->`` with shared footer markup."""
    async with aiofiles.open(page_path, encoding="utf-8") as f:
        html_content = await f.read()
    if "<!-- SITE_FOOTER -->" in html_content:
        html_content = html_content.replace("<!-- SITE_FOOTER -->", FOOTER_HTML, 1)
    return HTMLResponse(content=html_content)


@app.get("/")
async def get_root() -> HTMLResponse:
    return await _html_with_injected_footer(INDEX_PATH)


@app.get("/room/{room_id}")
async def get_room(room_id: RoomIdPath) -> HTMLResponse:
    _ = room_id  # validated path param; HTML shell is the same for every room
    return await _html_with_injected_footer(ROOM_PATH)


@app.get("/polityka-prywatnosci")
async def get_polityka_prywatnosci() -> HTMLResponse:
    return await _html_with_injected_footer(POLITYKA_PATH)


@app.get("/cookies")
async def get_cookies_policy() -> HTMLResponse:
    return await _html_with_injected_footer(COOKIES_LEGAL_PATH)


@app.get("/regulamin")
async def get_regulamin() -> HTMLResponse:
    return await _html_with_injected_footer(REGULAMIN_PATH)


# Service worker must be served from a top-level scope to control all routes.
@app.get("/sw.js")
async def get_service_worker() -> FileResponse:
    return FileResponse(SW_PATH, media_type="application/javascript")


@app.get("/manifest.json")
async def get_manifest() -> FileResponse:
    return FileResponse(MANIFEST_PATH, media_type="application/manifest+json")


@app.get(
    "/api/share/{room_id}",
    responses={
        404: {"description": "Brak zapisanego wyniku dla tego pokoju."},
    },
)
async def get_share_json(room_id: RoomIdPath) -> ShareSnapshotOut:
    """JSON z wynikiem zakończonej gry (np. dla klienta lub integracji)."""
    from .share_store import get_snapshot

    snap = get_snapshot(room_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Brak zapisanego wyniku dla tego pokoju.")
    return ShareSnapshotOut(
        room_id=snap.room_id, host_name=snap.host_name, scores=dict(snap.scores)
    )


@app.get(
    "/share/{room_id}",
    responses={
        404: {"description": "Brak zapisanego wyniku dla tego kodu pokoju."},
    },
)
async def get_share_page(room_id: RoomIdPath) -> HTMLResponse:
    """Lekka strona z meta OG dla podglądu linków (Messenger, itp.)."""
    from .share_store import get_snapshot

    snap = get_snapshot(room_id)
    if snap is None:
        body = (
            '<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"/>'
            '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
            '<link rel="stylesheet" href="/static/css/style.css"/>'
            '<link rel="stylesheet" href="/static/css/site-footer.css"/>'
            "<title>Wynik — brak danych</title></head>"
            '<body class="share-page"><main class="page-wrapper"><div class="container">'
            '<section class="share-card room-glass-panel"><h1>Brak wyniku</h1>'
            "<p>Nie ma zapisanego wyniku dla tego kodu.</p>"
            '<p><a href="/">Strona główna</a></p></section></div></main></body></html>'
        )
        return HTMLResponse(content=body, status_code=404)
    title = f"Państwa-Miasta — wynik ({escape(snap.room_id)})"
    score_rows = "".join(
        f'<li><span class="share-score-name">{escape(n)}</span>'
        f'<span class="share-score-pts">{s} pkt</span></li>'
        for n, s in sorted(snap.scores.items(), key=lambda x: (-x[1], x[0]))
    )
    desc = (
        f"Host: {escape(snap.host_name or '—')}. "
        + ", ".join(
            f"{escape(n)}: {s}" for n, s in sorted(snap.scores.items(), key=lambda x: (-x[1], x[0]))
        )[:500]
    )
    body = (
        f'<!DOCTYPE html><html lang="pl"><head><meta charset="utf-8"/>'
        f'<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        f'<link rel="stylesheet" href="/static/css/style.css"/>'
        f'<link rel="stylesheet" href="/static/css/site-footer.css"/>'
        f"<title>{title}</title>"
        f'<meta property="og:title" content="{escape(title)}" />'
        f'<meta property="og:description" content="{escape(desc)}" />'
        f'<meta name="description" content="{escape(desc)}" />'
        f'</head><body class="share-page"><nav class="navbar"><div class="nav-container">'
        f'<a href="/" class="logo" style="text-decoration:none;">Państwa<span>Miasta</span></a>'
        f'</div></nav><main class="page-wrapper"><div class="container">'
        f'<section class="share-card room-glass-panel">'
        f'<h1>Wynik pokoju <span class="share-room-code">{escape(snap.room_id)}</span></h1>'
        f'<p class="share-host"><strong>Host:</strong> {escape(snap.host_name or "—")}</p>'
        f'<ol class="share-score-list">{score_rows}</ol>'
        f'<p class="share-actions"><a class="btn-secondary" href="/">Strona główna</a> '
        f'<a class="btn-secondary" href="/room/{escape(snap.room_id)}">Pokój</a></p>'
        f"</section></div></main></body></html>"
    )
    return HTMLResponse(content=body)


@app.get("/api/active-rooms")
async def get_active_rooms() -> list[ActiveRoomRow]:
    return [
        ActiveRoomRow(
            id=r_id,
            players=len(room.connections),
            host=room.host_name or "Anonim",
            current_round=room.current_round,
            max_rounds=room.max_rounds,
            time_limit=room.time_limit,
            visibility=cast(Literal["public", "private"], room.visibility),
            visibility_label=("Publiczny" if room.visibility == "public" else "Prywatny"),
        )
        for r_id, room in manager.rooms.items()
        if room_listed_in_active_lobby(room)
    ]


@app.post("/api/quick-join", response_model=QuickJoinOut)
async def post_quick_join() -> QuickJoinOut:
    room_id, created, max_rounds, time_limit = manager.pick_quick_join_room()
    return QuickJoinOut(
        room_id=room_id,
        created=created,
        max_rounds=max_rounds,
        time_limit=time_limit,
    )


@app.post("/api/rooms/{room_id}/appeals", response_model=AppealOut)
async def post_room_appeal(room_id: RoomIdPath, body: AppealIn) -> AppealOut:
    result = await submit_appeal(
        manager,
        room_id,
        body.player_name,
        body.round,
        body.category,
    )
    return AppealOut.model_validate(result)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


async def _send_initial_state(websocket: WebSocket, room, client_name: str) -> None:
    """Broadcast join messages and resume state if a round is in progress."""
    await room.broadcast(
        json.dumps({"type": "system", "message": f"{client_name} dołączył do gry"})
    )
    await room.broadcast(json.dumps(score_update_payload(room)))

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
                    "resume": True,
                }
            )
        )
    elif room.game_over:
        round_history = list(room.round_history)
        if not round_history:
            stored = await fetch_game_transcript(room.room_id)
            if isinstance(stored, dict) and isinstance(stored.get("rounds"), list):
                round_history = stored["rounds"]
        await websocket.send_text(
            json.dumps(
                {
                    "type": "round_results",
                    "room_id": room.room_id,
                    "answers": {},
                    "round_scores": {},
                    "total_scores": room.scores,
                    "game_over": True,
                    "host_name": room.host_name,
                    "final": True,
                    "round_history": round_history,
                }
            )
        )
    elif room.results_phase_active:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "round_results",
                    "room_id": room.room_id,
                    "answers": room.answers_received,
                    "round_scores": room.provisional_round_scores,
                    "total_scores": room.scores,
                    "game_over": False,
                    "host_name": room.host_name,
                    "final": False,
                    "veto_tallies": room.veto_tallies(),
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
        if room.is_playing:
            manager.cancel_lobby_idle(room)
        else:
            manager.touch_lobby_idle(room, reset=True)
    elif msg_type == "not_ready":
        await handle_not_ready(room, client_name)
        manager.touch_lobby_idle(room, reset=True)
    elif msg_type == "restart_game":
        await handle_restart_game(room, client_name, msg)
        manager.touch_lobby_idle(room, reset=True)
    elif msg_type == "dissolve_room":
        manager.cancel_lobby_idle(room)
        await handle_dissolve_room(room, room_id, client_name, delete_room_immediate)
    elif msg_type == "stop":
        await handle_stop(room, room_id, client_name, force_end_round)
    elif msg_type == "answers":
        await handle_answers(room, room_id, client_name, msg, global_round_timeout)
    elif msg_type == "veto_vote":
        await handle_veto_vote(room, client_name, msg)
    elif msg_type == "kick_player":
        await handle_kick_player(room, room_id, client_name, msg, manager)
    else:
        logger.warning(f"Unknown message type '{msg_type}' from '{client_name}'")


@app.websocket("/ws/{room_id}/{client_name}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: RoomIdPath,
    client_name: ClientNamePath,
    rounds: Annotated[int, Query(ge=1, le=50)] = 5,
    limit: Annotated[int, Query(ge=10, le=600)] = 90,
    visibility: Annotated[Literal["public", "private"], Query()] = "public",
) -> None:
    logger.info(
        f"WebSocket attempt: room={room_id}, client={client_name}, "
        f"rounds={rounds}, limit={limit}, visibility={visibility}"
    )
    client_ip = client_ip_from_websocket(websocket)
    success, reject_reason = await manager.connect(
        websocket, room_id, client_name, rounds, limit, visibility, client_ip=client_ip
    )
    if not success:
        logger.warning(
            "Connection rejected for %s in room %s (%s)",
            client_name,
            room_id,
            reject_reason,
        )
        close_code = 4408 if reject_reason == "room_full" else 1008
        await websocket.close(code=close_code)
        return

    room = manager.rooms.get(room_id)
    if room is None:
        logger.error("Room missing after successful connect: room_id=%s", room_id)
        await websocket.close(code=1011)
        return
    await _send_initial_state(websocket, room, client_name)

    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Raw data from '{client_name}': {data}")
            try:
                msg = ws_inbound_adapter.validate_json(data)
                await _dispatch(msg.model_dump(), room, room_id, client_name)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from '{client_name}': {data}")
            except ValidationError as exc:
                logger.warning(
                    "Invalid WS payload from %r in %s: %s",
                    client_name,
                    room_id,
                    exc,
                )
                with suppress(Exception):
                    await websocket.send_json({"type": "error", "message": "Invalid message"})
            except Exception as exc:
                logger.exception(f"Error handling message from '{client_name}': {exc}")
    except WebSocketDisconnect:
        logger.info(f"WebSocketDisconnect: '{client_name}' left room {room_id}")
        if not manager.disconnect(room_id, client_name, websocket):
            return
        if room_id not in manager.rooms:
            # Pusty pokój: `disconnect` już zaplanował opóźnione `delete_room`.
            return
        room = manager.rooms[room_id]
        await room.broadcast(
            json.dumps({"type": "system", "message": f"{client_name} opuścił grę"})
        )
        await room.broadcast(json.dumps(score_update_payload(room)))
        logger.info(f"Notified room {room_id} about departure of '{client_name}'")
