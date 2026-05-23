"""Wewnętrzne API kolejki słów dla automatyzacji (n8n)."""

from __future__ import annotations

import os
import secrets
from typing import Literal

from fastapi import HTTPException

from .db import decide_pending_dictionary_suggestion, list_pending_dictionary_suggestions

DecisionStatus = Literal["accepted", "rejected", "error"]


def words_worker_token() -> str:
    return (os.environ.get("PM_WORDS_WORKER_TOKEN") or "").strip()


def words_worker_configured() -> bool:
    return bool(words_worker_token())


def verify_words_worker_token(authorization: str | None) -> None:
    expected = words_worker_token()
    if not expected:
        raise HTTPException(status_code=503, detail="Worker kolejki słów jest wyłączony.")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Brak tokenu worker.")
    provided = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Nieprawidłowy token worker.")


def _serialize_row(row: dict) -> dict:
    return {
        "id": int(row["id"]),
        "category": str(row["category"]),
        "proposed_display": str(row["proposed_display"]),
        "proposed_norm": str(row["proposed_norm"]),
        "target_seed": str(row["target_seed"]),
        "letter": str(row["letter"]),
        "room_id": str(row["room_id"]),
        "player_name": str(row["player_name"]),
        "round": int(row["round"]),
        "created_at": int(row["created_at"]),
    }


async def fetch_pending_batch(*, limit: int, after_id: int) -> dict:
    rows = await list_pending_dictionary_suggestions(limit=limit, after_id=after_id)
    items = [_serialize_row(row) for row in rows]
    next_after_id = items[-1]["id"] if items else after_id
    return {"items": items, "next_after_id": next_after_id}


async def apply_worker_decision(
    suggestion_id: int,
    *,
    status: DecisionStatus,
    ai_explanation: str | None,
    review_note: str | None,
) -> dict:
    outcome = await decide_pending_dictionary_suggestion(
        suggestion_id,
        status,
        review_note=review_note,
        ai_explanation=ai_explanation,
    )
    if outcome == "missing":
        raise HTTPException(status_code=404, detail="Nie znaleziono zgłoszenia.")
    if outcome == "not_pending":
        raise HTTPException(status_code=409, detail="Zgłoszenie nie jest już w stanie pending.")
    return {"suggestion_id": suggestion_id, "status": status}
