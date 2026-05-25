"""HTTP API statystyk z rozegranych gier."""

from __future__ import annotations

import json
import time
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
    """Zwraca top 5 najczesciej podawanych panstw na dzisiejsza litere.

    Liczy odsetek gier (nie odpowiedzi) w ostatnich 30 dniach,
    w ktorych padlo dane panstwo na litere dnia.
    """
    letter = _daily_letter()
    cutoff = int(time.time()) - 30 * 86400

    counts: dict[str, int] = {}
    total_games_with_letter = 0

    async with connect() as db:
        async with db.execute(
            "SELECT payload FROM game_transcripts WHERE finished_at >= ? ORDER BY finished_at DESC",
            (cutoff,),
        ) as cursor:
            rows = await cursor.fetchall()

    for row in rows:
        payload_json = row["payload"]
        try:
            data = json.loads(payload_json)
        except (json.JSONDecodeError, TypeError):
            continue
        rounds = data.get("rounds", [])
        found_letter = False
        countries_in_game: set[str] = set()

        for rnd in rounds:
            if rnd.get("letter", "").upper() != letter:
                continue
            found_letter = True
            answers = rnd.get("answers", {})
            for player_answers in answers.values():
                kraj = (player_answers.get("Państwo") or "").strip()
                if not kraj or not kraj[0].upper() == letter:
                    continue
                countries_in_game.add(kraj.capitalize())

        if found_letter:
            total_games_with_letter += 1
            for kraj in countries_in_game:
                counts[kraj] = counts.get(kraj, 0) + 1

    sorted_items = sorted(counts.items(), key=lambda x: (-x[1], x[0]))[:5]

    total = total_games_with_letter or 1
    top = [
        {
            "name": name,
            "count": count,
            "pct": round(count / total * 100, 1),
        }
        for name, count in sorted_items
    ]

    return {
        "letter": letter,
        "date": date.today().isoformat(),
        "total_games": total_games_with_letter,
        "top": top,
    }
