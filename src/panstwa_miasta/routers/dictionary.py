"""HTTP API recznej kolejki slownika (bez AI)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..api_models import WordReportIn, WordReportOut
from ..db_backend import connect
from ..word_queue import submit_dictionary_intake

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])

# Kategorie dostepne w slowniku (bez panstw — trywialne)
SLOWNIK_TABLES = {
    "miasta": "cities",
    "rosliny": "plant_norms",
    "zwierzeta": "animal_norms",
    "zawody": "jobs",
    "imiona": "names",
    "rzeczy": "things",
}


@router.get("/slownik/{category}/{letter}")
async def get_slownik_words(category: str, letter: str, limit: int = 100):
    """Zwraca slowa dla kategorii + litery z Turso."""
    table = SLOWNIK_TABLES.get(category)
    if not table:
        raise HTTPException(404, f"Nieznana kategoria: {category}")
    letter_upper = letter.strip().upper()
    if len(letter_upper) != 1:
        raise HTTPException(400, "Podaj pojedyncza litere")

    async with connect() as db:
        if category == "miasta":
            cur = await db.execute(
                "SELECT name FROM cities WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"{letter_upper}%", limit),
            )
        elif category in ("rosliny", "zwierzeta"):
            cur = await db.execute(
                f"SELECT norm FROM {table} WHERE norm LIKE ? ORDER BY norm LIMIT ?",
                (f"{letter_upper}%", limit),
            )
        elif category == "imiona":
            cur = await db.execute(
                "SELECT name FROM names WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"{letter_upper}%", limit),
            )
        elif category == "zawody":
            cur = await db.execute(
                "SELECT name FROM jobs WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"{letter_upper}%", limit),
            )
        else:  # rzeczy
            cur = await db.execute(
                "SELECT name FROM things WHERE name LIKE ? ORDER BY name LIMIT ?",
                (f"{letter_upper}%", limit),
            )
        rows = await cur.fetchall()
        return {"category": category, "letter": letter_upper, "words": [r[0] for r in rows]}


@router.get("/slownik/categories")
async def get_slownik_categories():
    """Zwraca liste kategorii z liczba slow."""
    async with connect() as db:
        result = {}
        for cat, table in SLOWNIK_TABLES.items():
            cur = await db.execute(f"SELECT count(*) FROM {table}")
            row = await cur.fetchone()
            result[cat] = row[0] if row else 0
        return result


@router.post("/suggestions")
async def post_dictionary_suggestion(body: WordReportIn) -> WordReportOut:
    result = await submit_dictionary_intake(
        word=body.word,
        category=body.category,
        letter=body.starting_letter,
    )
    return WordReportOut.model_validate(result)
