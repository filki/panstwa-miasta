"""Kolejka crowdsourcingu słów (RAG) na tabeli ``dictionary_suggestions``."""

from __future__ import annotations

import os
from datetime import UTC, datetime

from fastapi import HTTPException

from .db import (
    fetch_latest_dictionary_suggestion,
    normalize_dictionary_suggestion_status,
    report_dictionary_suggestion,
)
from .manager import GAME_CATEGORIES, normalize_text

_CATEGORY_TO_SEED: dict[str, str] = {
    "Państwo": "countries",
    "Miasto": "cities",
    "Imię": "names",
    "Zawód": "jobs",
    "Zwierzę": "animals",
    "Roślina": "plants",
    "Rzecz": "things",
}


def rag_queue_enabled() -> bool:
    return (os.environ.get("PM_RAG_QUEUE_ENABLED") or "").lower() in ("1", "true", "yes")


def _normalize_letter(letter: str) -> str:
    cleaned = letter.strip().lower()
    if len(cleaned) != 1:
        raise HTTPException(status_code=422, detail="Litera musi być pojedynczym znakiem.")
    return cleaned


def _target_seed_for_category(category: str) -> str:
    return _CATEGORY_TO_SEED.get(category, "")


def _format_created_at(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


async def submit_word_report(*, word: str, category: str, letter: str) -> dict:
    if not rag_queue_enabled():
        raise HTTPException(status_code=503, detail="Kolejka weryfikacji AI jest wyłączona.")
    if category not in GAME_CATEGORIES:
        raise HTTPException(status_code=422, detail="Nieznana kategoria.")
    cleaned_word = word.strip()
    if not cleaned_word:
        raise HTTPException(status_code=422, detail="Słowo nie może być puste.")
    normalized_letter = _normalize_letter(letter)
    outcome, suggestion_id = await report_dictionary_suggestion(
        category=category,
        word=cleaned_word,
        letter=normalized_letter,
        target_seed=_target_seed_for_category(category),
    )
    return {
        "outcome": outcome,
        "suggestion_id": suggestion_id,
        "message_pl": (
            "To słowo jest już w kolejce weryfikacji AI."
            if outcome == "exists"
            else "Dziękujemy — AI sprawdzi to słowo."
        ),
    }


async def lookup_word_reason(*, word: str, category: str, letter: str) -> dict:
    if not rag_queue_enabled():
        raise HTTPException(status_code=503, detail="Kolejka weryfikacji AI jest wyłączona.")
    if category not in GAME_CATEGORIES:
        raise HTTPException(status_code=422, detail="Nieznana kategoria.")
    cleaned_word = word.strip()
    if not cleaned_word:
        raise HTTPException(status_code=422, detail="Słowo nie może być puste.")
    normalized_letter = _normalize_letter(letter)
    row = await fetch_latest_dictionary_suggestion(
        category=category,
        proposed_norm=normalize_text(cleaned_word),
        letter=normalized_letter,
    )
    if row is None:
        return {
            "status": "missing",
            "message_pl": "Brak zgłoszenia tego słowa w kolejce.",
            "ai_reason": None,
            "created_at": None,
        }
    status = normalize_dictionary_suggestion_status(str(row["status"]))
    ai_reason = str(row.get("ai_explanation") or row.get("review_note") or "").strip() or None
    if status == "pending":
        message = "W kolejce weryfikacji AI."
    elif status == "accepted":
        message = "Słowo zostało zaakceptowane przez weryfikację AI."
    elif status == "rejected":
        message = "Słowo zostało odrzucone przez weryfikację AI."
    elif status == "error":
        message = "Weryfikacja AI zakończyła się błędem — spróbuj ponownie później."
    else:
        message = "Nieznany status zgłoszenia."
    return {
        "status": status,
        "message_pl": message,
        "ai_reason": ai_reason,
        "created_at": _format_created_at(int(row["created_at"])),
    }
