import asyncio
import json
import os
import pathlib
import time
from contextlib import asynccontextmanager, suppress
from datetime import date
from html import escape
from typing import Annotated, Literal, cast

import aiofiles
import aiosqlite
from fastapi import FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from .analytics_snippet import inject_before_head_close, public_head_snippets
from .api_models import (
    ActiveRoomRow,
    AppealIn,
    AppealOut,
    ClientNamePath,
    CreateRoomOut,
    LobbyConfigIn,
    QuickJoinOut,
    RoomIdPath,
    ShareSnapshotOut,
)
from .appeal_tokens import issue_appeal_token, verify_appeal_token
from .appeals_service import submit_appeal
from .constants import STOP_SUBMIT_GRACE_SECONDS, STOP_SUBMIT_SECONDS
from .data import (
    reload_countries,
    reload_jobs,
    reload_miasta,
    reload_names,
    reload_rosliny,
    reload_things,
    reload_zwierzeta,
)
from .db import delete_room, fetch_game_transcript, fetch_room_snapshot, init_db, save_room
from .db_backend import connect
from .db_redis import close_redis, connect_redis, redis_configured, redis_ping
from .handlers import (
    _begin_results_phase,
    handle_add_custom_category,
    handle_answers,
    handle_chat,
    handle_dissolve_room,
    handle_kick_player,
    handle_lobby_chat,
    handle_lobby_config_update,
    handle_not_ready,
    handle_ready,
    handle_remove_custom_category,
    handle_restart_game,
    handle_stop,
    handle_veto_vote,
    lobby_state_payload,
    score_update_payload,
)
from .limits import (
    check_http_rate_limit,
    check_ws_message_rate,
    client_ip_from_request,
    client_ip_from_websocket,
    http_rate_bucket_name,
)
from .logger import get_logger
from .manager import ConnectionManager, room_listed_in_active_lobby
from .routers.dictionary import router as dictionary_router
from .routers.stats import router as stats_router
from .routers.words import router as words_router
from .routers.words_worker import router as words_worker_router
from .ws_messages import ws_inbound_adapter

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Base URL — wstrzykiwane do HTML zamiast hardcoded
# ---------------------------------------------------------------------------
_BASE_URL_PLACEHOLDER = "{{BASE_URL}}"
PM_BASE_URL = (
    os.environ.get(
        "PM_BASE_URL",
        "https://panstwamiasta.com.pl/",
    ).rstrip("/")
    + "/"
)

# Dev environment detection — injects a visual badge
_PM_IS_DEV = PM_BASE_URL != "https://panstwamiasta.com.pl/"
_DEV_RIBBON_HTML = (
    (
        '<div id="pm-dev-ribbon" style="'
        "position:fixed;top:0;left:0;right:0;z-index:9999;"
        "background:#dc2626;color:#fff;text-align:center;"
        "padding:2px 0;font-size:0.7rem;font-weight:700;"
        "letter-spacing:2px;text-transform:uppercase"
        '">ŚRODOWISKO DEV</div>'
    )
    if _PM_IS_DEV
    else ""
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    t0 = time.monotonic()

    def _step(label: str, since: float) -> float:
        now = time.monotonic()
        logger.info("Startup %s (%.1fs since previous)", label, now - since)
        return now

    logger.info("Application startup: initializing DB and loading rooms")
    await init_db()
    t = _step("init_db done", t0)
    await reload_countries()
    t = _step("reload_countries done", t)
    await reload_miasta()
    t = _step("reload_miasta done", t)
    await reload_names()
    t = _step("reload_names done", t)
    await reload_jobs()
    t = _step("reload_jobs done", t)
    await reload_things()
    t = _step("reload_things done", t)
    await reload_zwierzeta()
    t = _step("reload_zwierzeta done", t)
    await reload_rosliny()
    t = _step("reload_rosliny done", t)
    await manager.load_from_db()
    _step("load_from_db done", t)
    if redis_configured():
        await connect_redis()
        _step("redis connect done", t)
    logger.info("Startup completed (total %.1fs)", time.monotonic() - t0)
    yield
    await close_redis()
    logger.info("Redis connection closed")
    logger.info("Application shutdown")


app = FastAPI(title="Państwa-Miasta Engine", lifespan=lifespan)

# Zezwalaj Capacitor WebView (Android: http://localhost, iOS: capacitor://localhost)
# oraz produkcję https://panstwamiasta.com.pl i local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:*",
        "capacitor://localhost",
        "https://panstwamiasta.com.pl",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stats_router)
app.include_router(words_router)
app.include_router(dictionary_router)
app.include_router(words_worker_router)
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
        or request.url.path
        in (
            "/api/quick-join",
            "/api/rooms",
            "/api/words/report",
            "/api/words/check-reason",
            "/api/dictionary/suggestions",
        )
        or request.url.path.startswith("/api/internal/words/")
        or request.url.path.endswith("/appeals")
    ):
        ip = client_ip_from_request(request)
        blocked = await check_http_rate_limit(ip, bucket)
        if blocked is not None:
            return blocked
    return await call_next(request)


# Montowanie plików statycznych — custom wrapper dla {{BASE_URL}} w HTML
static_path = pathlib.Path(__file__).parent.parent.parent / "static"


class _BaseUrlStaticFiles(StaticFiles):
    """Injects {{BASE_URL}} into served HTML files."""

    async def get_response(self, path: str, scope):
        if path in {"index.html", "room.html"}:
            return await _html_with_injected_footer(static_path / path)
        return await super().get_response(path, scope)


app.mount("/static", _BaseUrlStaticFiles(directory=static_path), name="static")


INDEX_PATH = static_path / "index.html"
ROOM_PATH = static_path / "room.html"
SW_PATH = static_path / "sw.js"
MANIFEST_PATH = static_path / "manifest.json"
POLITYKA_PATH = static_path / "polityka-prywatnosci.html"
COOKIES_LEGAL_PATH = static_path / "cookies.html"
REGULAMIN_PATH = static_path / "regulamin.html"
SLOWNIK_PATH = static_path / "slownik.html"
FOOTER_PARTIAL_PATH = static_path / "partials" / "site-footer.html"
FOOTER_HTML = FOOTER_PARTIAL_PATH.read_text(encoding="utf-8")
SITE_PUBLIC_ORIGIN = "https://panstwamiasta.com.pl"


def _sitemap_lastmod() -> str:
    try:
        return date.fromtimestamp(INDEX_PATH.stat().st_mtime).isoformat()
    except OSError:
        return date.today().isoformat()


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
        room.mark_stop_phase_started()
        await room.broadcast(
            json.dumps(
                {
                    "type": "stop_round",
                    "sender": "System (Koniec czasu)",
                    "time_left": STOP_SUBMIT_SECONDS,
                }
            )
        )
        # Store task reference to prevent premature GC (SonarQube MAJOR)
        task = asyncio.ensure_future(force_end_round(room_id))
        room._global_timeout_task = task
        logger.info(f"Global timeout fired for room {room_id}, round {round_num}")


async def force_end_round(room_id: str) -> None:
    """Forces round results after the post-stop submit window."""
    await asyncio.sleep(STOP_SUBMIT_SECONDS + STOP_SUBMIT_GRACE_SECONDS)
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


_FOOTER_PLACEHOLDER = "<!-- SITE_FOOTER -->"


async def _html_with_injected_footer(page_path: pathlib.Path) -> HTMLResponse:
    """Serves HTML and replaces footer placeholder with shared footer markup."""
    async with aiofiles.open(page_path, encoding="utf-8") as f:
        html_content = await f.read()
    if _FOOTER_PLACEHOLDER in html_content:
        html_content = html_content.replace(_FOOTER_PLACEHOLDER, FOOTER_HTML, 1)
    if _BASE_URL_PLACEHOLDER in html_content:
        html_content = html_content.replace(_BASE_URL_PLACEHOLDER, PM_BASE_URL, 1)
    html_content = inject_before_head_close(html_content, public_head_snippets())
    if _DEV_RIBBON_HTML:
        html_content = inject_before_head_close(html_content, _DEV_RIBBON_HTML)
    return HTMLResponse(content=html_content)


async def _html_with_meta(page_path: pathlib.Path, extra_head: str) -> HTMLResponse:
    """Like _html_with_injected_footer but with extra meta tags injected."""
    async with aiofiles.open(page_path, encoding="utf-8") as f:
        html_content = await f.read()
    if _FOOTER_PLACEHOLDER in html_content:
        html_content = html_content.replace(_FOOTER_PLACEHOLDER, FOOTER_HTML, 1)
    if _BASE_URL_PLACEHOLDER in html_content:
        html_content = html_content.replace(_BASE_URL_PLACEHOLDER, PM_BASE_URL, 1)
    html_content = inject_before_head_close(html_content, public_head_snippets())
    if _DEV_RIBBON_HTML:
        html_content = inject_before_head_close(html_content, _DEV_RIBBON_HTML)
    html_content = _replace_room_head(html_content, extra_head)
    return HTMLResponse(content=html_content)


def _replace_room_head(html: str, extra: str) -> str:
    """Zastąp statyczny <title> i wstrzyknij extra meta przed </head>."""
    # Nadpisz fallback title z room.html
    html = html.replace(
        "<title>Państwa-Miasta Online — dołącz do gry</title>",
        "",
        1,
    )
    return inject_before_head_close(html, extra)


def _html_with_analytics(html: str) -> str:
    return inject_before_head_close(html, public_head_snippets())


@app.get("/")
async def get_root() -> HTMLResponse:
    return await _html_with_injected_footer(INDEX_PATH)


@app.get("/room/{room_id}")
async def get_room(room_id: RoomIdPath) -> HTMLResponse:
    # Sprawdź w DB czy pokój istnieje i jest publiczny
    try:
        snap = await fetch_room_snapshot(room_id)
    except Exception:
        snap = None
    if snap is not None:
        vis = str(snap.get("visibility", "public") or "public")
        if vis == "public":
            # Publiczny pokój → dynamiczne meta tagi
            safe_id = escape(room_id, quote=True)
            dyn_title = f"Państwa-Miasta online — pokój {safe_id} | Gra ze znajomymi"
            dyn_desc = (
                f"Dołącz do gry Państwa-Miasta w pokoju {safe_id}. "
                "Graj online ze znajomymi w przeglądarce, bez logowania."
            )
            extra = (
                f"<title>{dyn_title}</title>\n"
                f'<meta name="description" content="{dyn_desc}" />\n'
                f'<meta property="og:title" content="{dyn_title}" />\n'
                f'<meta property="og:description" content="{dyn_desc}" />\n'
                f'<meta name="twitter:title" content="{dyn_title}" />\n'
                f'<meta name="twitter:description" content="{dyn_desc}" />\n'
            )
        else:
            # Prywatny pokój — nie indeksuj
            extra = '<meta name="robots" content="noindex, nofollow" />\n'
        return await _html_with_meta(ROOM_PATH, extra)
    # Nieznany pokój — noindex
    extra = '<meta name="robots" content="noindex, nofollow" />\n'
    return await _html_with_meta(ROOM_PATH, extra)


@app.get("/polityka-prywatnosci")
async def get_polityka_prywatnosci() -> HTMLResponse:
    return await _html_with_injected_footer(POLITYKA_PATH)


@app.get("/cookies")
async def get_cookies_policy() -> HTMLResponse:
    return await _html_with_injected_footer(COOKIES_LEGAL_PATH)


@app.get("/regulamin")
async def get_regulamin() -> HTMLResponse:
    return await _html_with_injected_footer(REGULAMIN_PATH)


@app.get("/slownik")
async def get_slownik() -> HTMLResponse:
    return await _html_with_injected_footer(SLOWNIK_PATH)


@app.get("/robots.txt", response_class=PlainTextResponse)
async def get_robots_txt() -> PlainTextResponse:
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/\n"
        "Disallow: /ws/\n"
        "Disallow: /share/\n"
        f"Sitemap: {SITE_PUBLIC_ORIGIN}/sitemap.xml\n"
    )
    return PlainTextResponse(content=body)


@app.get("/sitemap.xml")
async def get_sitemap_xml() -> Response:
    lastmod = _sitemap_lastmod()
    # Statyczne strony
    paths = ["/", "/polityka-prywatnosci", "/cookies", "/regulamin", "/slownik"]
    urls = "".join(
        f"<url><loc>{SITE_PUBLIC_ORIGIN}{path}</loc><lastmod>{lastmod}</lastmod></url>\n"
        for path in paths
    )
    # Publiczne pokoje z bazy (aktywne i nieaktywne — wszystkie publiczne)
    try:
        async with connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT room_id FROM rooms WHERE visibility = 'public' ORDER BY room_id"
            ) as cur:
                for row in await cur.fetchall():
                    rid = str(row["room_id"])
                    safe = escape(rid, quote=True)
                    urls += (
                        f"<url><loc>{SITE_PUBLIC_ORIGIN}/room/{safe}</loc>"
                        f"<lastmod>{lastmod}</lastmod></url>\n"
                    )
    except Exception:
        pass
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}"
        "</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


# Service worker must be served from a top-level scope to control all routes.
@app.get("/sw.js")
async def get_service_worker() -> FileResponse:
    return FileResponse(SW_PATH, media_type="application/javascript")


@app.get("/manifest.json")
async def get_manifest() -> FileResponse:
    return FileResponse(MANIFEST_PATH, media_type="application/manifest+json")


@app.get(
    "/healthz",
    responses={
        503: {"description": "Baza niedostępna."},
    },
)
async def get_healthz() -> dict[str, str]:
    result: dict[str, str] = {}
    try:
        async with connect() as db, db.execute("SELECT 1") as cur:
            await cur.fetchone()
        result["db"] = "ok"
    except Exception as exc:
        logger.warning("healthz DB check failed: %s", exc)
        result["db"] = "error"
    if redis_configured():
        try:
            redis_ok = await redis_ping()
            result["redis"] = "ok" if redis_ok else "error"
        except Exception as exc:
            logger.warning("healthz Redis check failed: %s", exc)
            result["redis"] = "error"
    status = "ok" if result.get("db") == "ok" and result.get("redis", "ok") == "ok" else "unhealthy"
    if status != "ok":
        raise HTTPException(status_code=503, detail=json.dumps(result))
    return {"status": "ok", **result}


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
            '<meta name="robots" content="noindex, nofollow">'
            '<link rel="stylesheet" href="/static/css/style.css"/>'
            '<link rel="stylesheet" href="/static/css/site-footer.css"/>'
            "<title>Wynik — brak danych</title></head>"
            '<body class="share-page"><main class="page-wrapper"><div class="container">'
            '<section class="share-card room-glass-panel"><h1>Brak wyniku</h1>'
            "<p>Nie ma zapisanego wyniku dla tego kodu.</p>"
            '<p><a href="/">Strona główna</a></p></section></div></main></body></html>'
        )
        return HTMLResponse(content=_html_with_analytics(body), status_code=404)
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
        f'<meta name="robots" content="noindex, nofollow">'
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
    return HTMLResponse(content=_html_with_analytics(body))


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


@app.get("/api/debug/rooms")
async def debug_rooms() -> dict:
    """Debug: pokazuje stan wewnętrzny wszystkich pokoi w RAM."""
    result = {}
    for r_id, room in manager.rooms.items():
        result[r_id] = {
            "connections": list(room.connections.keys()),
            "host": room.host_name,
            "current_round": room.current_round,
            "is_playing": room.is_playing,
            "game_over": room.game_over,
            "scores": dict(room.scores),
            "disconnected_players": dict(room.disconnected_players),
            "has_ws": [str(type(ws)) for ws in room.connections.values()],
        }
    return {"total": len(manager.rooms), "rooms": result}


@app.post("/api/quick-join")
async def post_quick_join() -> QuickJoinOut:
    room_id, created, max_rounds, time_limit = await manager.pick_quick_join_room()
    return QuickJoinOut(
        room_id=room_id,
        created=created,
        max_rounds=max_rounds,
        time_limit=time_limit,
    )


@app.post("/api/rooms")
async def post_create_room() -> CreateRoomOut:
    room_id = await manager.allocate_room_id()
    return CreateRoomOut(room_id=room_id)


@app.patch(
    "/api/rooms/{room_id}/config",
    responses={
        404: {"description": "Room not found"},
        403: {"description": "Only host can change config"},
        409: {"description": "Cannot change config during game"},
    },
)
async def patch_room_config(
    room_id: RoomIdPath,
    body: LobbyConfigIn,
    x_player_name: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    if room_id not in manager.rooms:
        raise HTTPException(status_code=404, detail="Room not found")
    room = manager.rooms[room_id]
    if not x_player_name or x_player_name != room.host_name:
        raise HTTPException(status_code=403, detail="Only host can change config")
    if room.is_playing or room.current_round > 0:
        raise HTTPException(status_code=409, detail="Cannot change config during game")

    room.max_rounds = body.rounds
    room.time_limit = body.limit
    room.visibility = body.visibility
    room.stop_mechanism = body.stop_mechanism

    await save_room(
        room_id,
        room.max_rounds,
        room.time_limit,
        room.current_round,
        room.host_name,
        room.visibility,
        stop_mechanism=int(room.stop_mechanism),
    )

    await room.broadcast(
        json.dumps(
            {
                "type": "lobby_config_update",
                "max_rounds": room.max_rounds,
                "time_limit": room.time_limit,
                "visibility": room.visibility,
                "stop_mechanism": room.stop_mechanism,
            }
        )
    )
    return {"status": "ok"}


def _appeal_bearer_token(authorization: str | None) -> str:
    if not authorization:
        return ""
    prefix = "bearer "
    if authorization.lower().startswith(prefix):
        return authorization[len(prefix) :].strip()
    return ""


@app.post(
    "/api/rooms/{room_id}/appeals",
    responses={
        401: {"description": "Brak uprawnień do odwołania."},
    },
)
async def post_room_appeal(
    room_id: RoomIdPath,
    body: AppealIn,
    authorization: Annotated[str | None, Header()] = None,
) -> AppealOut:
    token = _appeal_bearer_token(authorization)
    if not verify_appeal_token(room_id, body.player_name, token):
        raise HTTPException(status_code=401, detail="Brak uprawnień do odwołania.")
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
    await room.broadcast(json.dumps(lobby_state_payload(room)))

    if room.is_playing:
        resume_payload: dict[str, object] = {
            "type": "round_started",
            "letter": room.current_letter,
            "sender": "Serwer (Wznowienie)",
            "current_round": room.current_round,
            "max_rounds": room.max_rounds,
            "time_limit": room.time_limit,
            "resume": True,
            "stop_triggered": room.stop_triggered,
            "answer_submitted": client_name in room.answers_received,
        }
        seconds_left = room.round_seconds_remaining()
        if seconds_left is not None:
            resume_payload["seconds_left"] = seconds_left
        stop_left = room.stop_seconds_remaining()
        if stop_left is not None:
            resume_payload["stop_seconds_left"] = stop_left
        await websocket.send_text(json.dumps(resume_payload))
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
        token = issue_appeal_token(room.room_id, client_name)
        await websocket.send_text(json.dumps({"type": "appeal_token", "token": token}))
    elif room.results_phase_active:
        veto_ends_at = None
        if room.results_veto_ends_at is not None:
            veto_ends_at = int(room.results_veto_ends_at * 1000)
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
                    "veto_ends_at": veto_ends_at,
                    "categories": list(room.categories),
                    "custom_categories": dict(room.custom_categories),
                }
            )
        )


def _touch_lobby_after_ready(room) -> None:
    if room.is_playing:
        manager.cancel_lobby_idle(room)
    else:
        manager.touch_lobby_idle(room, reset=True)


async def _dispatch(msg: dict, room, room_id: str, client_name: str) -> None:
    """Route a message to the appropriate handler."""
    msg_type = msg.get("type")
    logger.info(f"Message '{msg_type}' from '{client_name}' in room {room_id}")

    if msg_type == "chat":
        await handle_chat(room, client_name, msg)
    elif msg_type == "ready":
        await handle_ready(room, room_id, client_name, global_round_timeout)
        _touch_lobby_after_ready(room)
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
    elif msg_type == "lobby_config_update":
        await handle_lobby_config_update(room, room_id, msg, client_name)
    elif msg_type == "add_custom_category":
        await handle_add_custom_category(room, room_id, msg, client_name)
    elif msg_type == "remove_custom_category":
        await handle_remove_custom_category(room, room_id, msg, client_name)
    elif msg_type == "lobby_chat_msg":
        await handle_lobby_chat(room, client_name, msg)
    elif msg_type is not None:
        logger.warning(f"Unknown message type '{msg_type}' from '{client_name}'")


async def _handle_ws_messages(
    websocket: WebSocket,
    room_id: str,
    room,
    client_name: str,
) -> None:
    """Process incoming WebSocket messages until disconnect."""
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug(f"Raw data from '{client_name}': {data}")
            if not await check_ws_message_rate(room_id, client_name):
                logger.warning(
                    "WS message rate limit exceeded for %r in %s",
                    client_name,
                    room_id,
                )
                with suppress(Exception):
                    await websocket.send_json(
                        {"type": "error", "message": "Zbyt wiele wiadomości."}
                    )
                await websocket.close(code=1008)
                return
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
        raise


@app.websocket("/ws/{room_id}/{client_name}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: RoomIdPath,
    client_name: ClientNamePath,
) -> None:
    logger.info(f"WebSocket attempt: room={room_id}, client={client_name}")
    client_ip = client_ip_from_websocket(websocket)
    success, reject_reason = await manager.connect(
        websocket, room_id, client_name, client_ip=client_ip
    )
    if not success:
        logger.warning(
            "Connection rejected for %s in room %s (%s)",
            client_name,
            room_id,
            reject_reason,
        )
        close_code = {
            "room_full": 4408,
            "game_in_progress": 4409,
        }.get(reject_reason or "", 1008)
        await websocket.close(code=close_code)
        return

    room = manager.rooms.get(room_id)
    if room is None:
        logger.error("Room missing after successful connect: room_id=%s", room_id)
        await websocket.close(code=1011)
        return
    await _send_initial_state(websocket, room, client_name)
    try:
        await _handle_ws_messages(websocket, room_id, room, client_name)
    except (WebSocketDisconnect, RuntimeError):
        logger.info(f"WebSocketDisconnect: '{client_name}' left room {room_id}")
        if not manager.disconnect(room_id, client_name, websocket):
            return
        if room_id not in manager.rooms:
            return
        was_host = room.host_name == client_name
        await manager.cleanup_player_after_disconnect(room_id, client_name)
        if room_id not in manager.rooms:
            return
        room = manager.rooms[room_id]
        await room.broadcast(
            json.dumps({"type": "system", "message": f"{client_name} opuścił grę"})
        )
        if was_host:
            manager._schedule_host_reassign(room, room_id, client_name)
        await room.broadcast(json.dumps(score_update_payload(room)))
        logger.info(f"Notified room {room_id} about departure of '{client_name}'")
