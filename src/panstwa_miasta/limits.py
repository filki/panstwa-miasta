"""Limity zasobów i lekkie rate-limiting (in-memory, na proces).

Wiele workerów uvicorn = osobne liczniki na proces; przed skalowaniem
poziomo warto dodać Redis lub jeden worker za reverse proxy.

Zmienne środowiskowe (opcjonalne, sensowne domyślne):

- ``PM_MAX_ROOMS`` — maks. liczba pokoi w pamięci (nowe pokoje są odrzucane).
- ``PM_WS_NEW_ROOMS_PER_IP_PER_MIN`` — max nowych pokoi na IP / min (sliding).
- ``PM_WS_CONNECTS_PER_IP_PER_MIN`` — max udanych połączeń WS na IP / min.
- ``PM_TRUST_X_FORWARDED_FOR`` — ``1`` / ``true``: pierwszy hop z ``X-Forwarded-For``
  (tylko za zaufanym proxy).
- ``PM_RATE_HTTP_API_ACTIVE``, ``PM_RATE_HTTP_API_SHARE``, ``PM_RATE_HTTP_SHARE_PAGE``,
  ``PM_RATE_HTTP_ROOM``, ``PM_RATE_HTTP_ROOT``, ``PM_RATE_HTTP_DEFAULT`` —
  max żądań GET+HEAD na IP w oknie ``PM_RATE_HTTP_WINDOW_SEC`` (domyślnie 60 s).
"""

from __future__ import annotations

import asyncio
import os
import time
from collections import defaultdict, deque

from fastapi import Request, WebSocket

_WS_WINDOW_SEC = 60.0
_HTTP_WINDOW_SEC = float(os.environ.get("PM_RATE_HTTP_WINDOW_SEC", "60") or "60")
if _HTTP_WINDOW_SEC < 1:
    _HTTP_WINDOW_SEC = 60.0

_lock = asyncio.Lock()
_ws_new_room_events: dict[str, deque[float]] = defaultdict(deque)
_ws_connect_events: dict[str, deque[float]] = defaultdict(deque)
_http_events: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def reset_counters_for_tests() -> None:
    """Czyści liczniki (tylko testy — brak synchronizacji z produkcyjnym ruchem)."""
    _ws_new_room_events.clear()
    _ws_connect_events.clear()
    _http_events.clear()


def _parse_positive_int(raw: str | None, default: int, *, upper: int) -> int:
    if raw is None or not str(raw).strip():
        return default
    try:
        v = int(str(raw).strip(), 10)
    except ValueError:
        return default
    return max(1, min(upper, v))


def max_rooms_cap() -> int:
    return _parse_positive_int(os.environ.get("PM_MAX_ROOMS"), 512, upper=100_000)


def max_players_per_room() -> int:
    return _parse_positive_int(os.environ.get("PM_MAX_PLAYERS_PER_ROOM"), 8, upper=64)


def ws_new_rooms_per_ip_per_min() -> int:
    return _parse_positive_int(os.environ.get("PM_WS_NEW_ROOMS_PER_IP_PER_MIN"), 24, upper=5000)


def ws_connects_per_ip_per_min() -> int:
    return _parse_positive_int(os.environ.get("PM_WS_CONNECTS_PER_IP_PER_MIN"), 200, upper=20_000)


def _http_limit_for_bucket(bucket: str) -> int:
    env_map = {
        "api_active": "PM_RATE_HTTP_API_ACTIVE",
        "api_quick_join": "PM_RATE_HTTP_API_QUICK_JOIN",
        "api_share": "PM_RATE_HTTP_API_SHARE",
        "share_page": "PM_RATE_HTTP_SHARE_PAGE",
        "room_html": "PM_RATE_HTTP_ROOM",
        "root": "PM_RATE_HTTP_ROOT",
        "default": "PM_RATE_HTTP_DEFAULT",
    }
    defaults = {
        "api_active": 40,
        "api_quick_join": 30,
        "api_share": 80,
        "share_page": 80,
        "room_html": 120,
        "root": 80,
        "default": 150,
    }
    env_key = env_map.get(bucket, "PM_RATE_HTTP_DEFAULT")
    return _parse_positive_int(os.environ.get(env_key), defaults.get(bucket, 150), upper=50_000)


def _monotonic() -> float:
    return time.monotonic()


def _purge(dq: deque[float], window: float, now: float) -> None:
    while dq and now - dq[0] > window:
        dq.popleft()


def client_ip_from_request(request: Request) -> str:
    trust = (os.environ.get("PM_TRUST_X_FORWARDED_FOR") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    if trust:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first[:128]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def client_ip_from_websocket(websocket: WebSocket) -> str:
    trust = (os.environ.get("PM_TRUST_X_FORWARDED_FOR") or "").lower() in (
        "1",
        "true",
        "yes",
    )
    if trust:
        xff = websocket.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first[:128]
    if websocket.client and websocket.client.host:
        return websocket.client.host
    return "unknown"


def http_rate_bucket_name(path: str) -> str | None:
    """Zwraca nazwę kubełka albo ``None`` — wtedy bez limitu HTTP."""
    if path.startswith("/static"):
        return None
    if path in ("/sw.js", "/manifest.json"):
        return None
    if path.startswith("/api/active-rooms"):
        return "api_active"
    if path.startswith("/api/quick-join"):
        return "api_quick_join"
    if path.startswith("/api/share/"):
        return "api_share"
    if path.startswith("/share/"):
        return "share_page"
    if path.startswith("/room/"):
        return "room_html"
    if path == "/":
        return "root"
    return "default"


async def check_http_rate_limit(client_ip: str, bucket: str):
    """Zwraca odpowiedź 429 albo ``None``, gdy żądanie może przejść dalej.

    W middleware Starlette nie wolno polegać na ``HTTPException`` z FastAPI —
    trzeba zwrócić konkretną odpowiedź.
    """
    from starlette.responses import JSONResponse

    limit = _http_limit_for_bucket(bucket)
    key = (client_ip, bucket)
    now = _monotonic()
    async with _lock:
        dq = _http_events[key]
        _purge(dq, _HTTP_WINDOW_SEC, now)
        if len(dq) >= limit:
            retry = max(1, int(_HTTP_WINDOW_SEC))
            return JSONResponse(
                status_code=429,
                content={"detail": "Zbyt wiele żądań, spróbuj za chwilę."},
                headers={"Retry-After": str(retry)},
            )
        dq.append(now)
    return None


async def check_ws_before_connect(client_ip: str, *, is_new_room: bool) -> bool:
    """``False`` gdy IP przekroczy limity (przed ``accept``)."""
    now = _monotonic()
    async with _lock:
        new_dq = _ws_new_room_events[client_ip]
        conn_dq = _ws_connect_events[client_ip]
        _purge(new_dq, _WS_WINDOW_SEC, now)
        _purge(conn_dq, _WS_WINDOW_SEC, now)
        if is_new_room and len(new_dq) >= ws_new_rooms_per_ip_per_min():
            return False
        if len(conn_dq) >= ws_connects_per_ip_per_min():
            return False
    return True


async def record_ws_connect_ok(client_ip: str, *, is_new_room: bool) -> None:
    """Wywołaj po udanym zapisie gracza / pokoju (tuż przed ``return True``)."""
    now = _monotonic()
    async with _lock:
        conn_dq = _ws_connect_events[client_ip]
        _purge(conn_dq, _WS_WINDOW_SEC, now)
        conn_dq.append(now)
        if is_new_room:
            new_dq = _ws_new_room_events[client_ip]
            _purge(new_dq, _WS_WINDOW_SEC, now)
            new_dq.append(now)
