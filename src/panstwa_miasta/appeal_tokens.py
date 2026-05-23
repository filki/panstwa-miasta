"""Krótkotrwałe tokeny odwołań po zakończeniu gry (w pamięci procesu)."""

from __future__ import annotations

import secrets
import time

_TTL_SEC = 86_400
_tokens: dict[tuple[str, str], tuple[str, float]] = {}


def clear_appeal_tokens_for_tests() -> None:
    _tokens.clear()


def _purge_expired(now: float) -> None:
    expired = [key for key, (_, exp) in _tokens.items() if exp <= now]
    for key in expired:
        _tokens.pop(key, None)


def issue_appeal_token(room_id: str, player_name: str) -> str:
    now = time.time()
    _purge_expired(now)
    token = secrets.token_urlsafe(32)
    _tokens[(room_id, player_name)] = (token, now + _TTL_SEC)
    return token


def verify_appeal_token(room_id: str, player_name: str, token: str) -> bool:
    if not token:
        return False
    now = time.time()
    _purge_expired(now)
    entry = _tokens.get((room_id, player_name))
    if entry is None:
        return False
    stored, exp = entry
    if exp <= now:
        _tokens.pop((room_id, player_name), None)
        return False
    return secrets.compare_digest(stored, token)
