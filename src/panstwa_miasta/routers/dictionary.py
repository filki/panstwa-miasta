"""HTTP API recznej kolejki slownika (bez AI)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..api_models import WordReportIn, WordReportOut
from ..data import JOBS, MIASTA, NAMES, ROSLINY, THINGS, ZWIERZETA
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
async def get_slownik_words(category: str, letter: str, limit: int = 200):
    """Zwraca slowa dla kategorii + litery z pamieci (ladowanej przy starcie)."""
    cat_map = {
        "miasta": MIASTA,
        "rosliny": ROSLINY,
        "zwierzeta": ZWIERZETA,
        "zawody": JOBS,
        "imiona": NAMES,
        "rzeczy": THINGS,
    }
    words = cat_map.get(category)
    if words is None:
        raise HTTPException(404, f"Nieznana kategoria: {category}")
    letter_upper = letter.strip().upper()
    if len(letter_upper) != 1:
        raise HTTPException(400, "Podaj pojedyncza litere")

    filtered = [w for w in words if w.upper().startswith(letter_upper)]
    filtered.sort()
    return {"category": category, "letter": letter_upper, "words": filtered[:limit]}


@router.get("/slownik/categories")
async def get_slownik_categories():
    """Zwraca liste kategorii z liczba slow."""
    return {
        "miasta": len(MIASTA),
        "rosliny": len(ROSLINY),
        "zwierzeta": len(ZWIERZETA),
        "zawody": len(JOBS),
        "imiona": len(NAMES),
        "rzeczy": len(THINGS),
    }


@router.post("/suggestions")
async def post_dictionary_suggestion(body: WordReportIn) -> WordReportOut:
    result = await submit_dictionary_intake(
        word=body.word,
        category=body.category,
        letter=body.starting_letter,
    )
    return WordReportOut.model_validate(result)
