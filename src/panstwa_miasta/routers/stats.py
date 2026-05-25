"""HTTP API statystyk z rozegranych gier."""

from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter

from ..db_backend import connect

router = APIRouter(prefix="/api/stats", tags=["stats"])

# Litery alfabetu (bez Q, X, V — rzadkie w polskich państwach)
DAILY_LETTERS = [
    "A",
    "B",
    "C",
    "D",
    "E",
    "F",
    "G",
    "H",
    "I",
    "J",
    "K",
    "L",
    "M",
    "N",
    "O",
    "P",
    "R",
    "S",
    "T",
    "U",
    "W",
    "Z",
]


def _daily_letter() -> str:
    """Wybierz litere dnia — stabilna przez cala dobe."""
    today = date.today()
    idx = (today.year * 365 + today.month * 31 + today.day) % len(DAILY_LETTERS)
    return DAILY_LETTERS[idx]


@router.get("/daily-top")
async def get_daily_top() -> dict:
    """Zwraca top 5 najczesciej podawanych panstw na dzisiejsza litere."""
    letter = _daily_letter()
    counts: dict[str, int] = {}

    async with connect() as db:
        async with db.execute(
            "SELECT payload FROM game_transcripts ORDER BY finished_at DESC LIMIT 500"
        ) as cursor:
            rows = await cursor.fetchall()

    for row in rows:
        payload_json = row["payload"]
        try:
            data = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            continue
        rounds = data.get("rounds", [])
        for rnd in rounds:
            if rnd.get("letter", "").upper() != letter:
                continue
            answers = rnd.get("answers", {})
            for player_answers in answers.values():
                kraj = (player_answers.get("Państwo") or "").strip().lower()
                if not kraj or not kraj.startswith(letter.lower()):
                    continue
                counts[kraj] = counts.get(kraj, 0) + 1

    top5 = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:5]

    return {
        "letter": letter,
        "date": date.today().isoformat(),
        "top": [{"name": name.capitalize(), "count": count} for name, count in top5],
    }
