"""HTTP API recznej kolejki slownika (bez AI)."""

from __future__ import annotations

import math

import aiosqlite
from fastapi import APIRouter, HTTPException

from ..api_models import WordReportIn, WordReportOut
from ..data import JOBS, MIASTA, NAMES, ROSLINY, THINGS, ZWIERZETA
from ..db_backend import _db_path
from ..word_queue import submit_dictionary_intake

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])

CAT_MAP = {
    "miasta": MIASTA,
    "rosliny": ROSLINY,
    "zwierzeta": ZWIERZETA,
    "zawody": JOBS,
    "imiona": NAMES,
    "rzeczy": THINGS,
}


@router.get("/slownik/{category}/{letter}")
async def get_slownik_words(category: str, letter: str, limit: int = 200):
    """Zwraca slowa dla kategorii + litery z pamieci (ladowanej przy starcie)."""
    words = CAT_MAP.get(category)
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


@router.get("/slownik/search")
async def search_slownik(
    q: str = "",
    category: str = "rosliny",
    page: int = 1,
    per_page: int = 10,
):
    """Wyszukiwarka słownikowa z paginacją.

    Dla kategorii ``imiona`` zwraca strukturę ``{imie, plec, liczebnosc}``
    z tabeli ``names`` w SQLite. Dla pozostałych kategorii zwraca listę
    słów z pamięci.
    """
    page = max(1, page)
    per_page = max(1, min(50, per_page))
    q = q.strip().lower()

    # --- Imiona: strukturalne zapytanie do SQLite ---
    if category == "imiona":
        async with aiosqlite.connect(_db_path()) as db:
            db.row_factory = aiosqlite.Row
            where = ""
            params: list[str] = []
            if q:
                where = "WHERE imie_norm LIKE ?"
                params = [q + "%"]
            # count
            async with db.execute(f"SELECT COUNT(*) as cnt FROM names {where}", params) as cur:
                cnt_row = await cur.fetchone()
                total = cnt_row["cnt"] if cnt_row else 0
            # data
            offset = (page - 1) * per_page
            async with db.execute(
                f"SELECT imie, plec, liczebnosc FROM names {where} ORDER BY liczebnosc DESC, imie ASC LIMIT ? OFFSET ?",
                params + [per_page, offset],
            ) as cur:
                rows = await cur.fetchall()
            words = [
                {"name": r["imie"], "gender": r["plec"], "count": r["liczebnosc"]} for r in rows
            ]
        pages = max(1, math.ceil(total / per_page))
        return {
            "category": "imiona",
            "query": q,
            "words": words,
            "total": total,
            "page": page,
            "pages": pages,
            "structured": True,
        }

    # --- Pozostałe kategorie: wyszukiwanie w pamięci ---
    words_set = CAT_MAP.get(category)
    if words_set is None:
        raise HTTPException(404, f"Nieznana kategoria: {category}")

    if not q or len(q) < 1:
        return {
            "category": category,
            "query": q,
            "words": [],
            "total": 0,
            "page": 1,
            "pages": 1,
            "structured": False,
        }

    # direct → prefix → substring
    direct = sorted(w for w in words_set if w.lower() == q)
    prefix = sorted(w for w in words_set if w.lower().startswith(q) and w.lower() != q)
    substring = sorted(
        w
        for w in words_set
        if q in w.lower() and w.lower() not in direct and w.lower() not in prefix
    )
    all_results = direct + prefix + substring
    total = len(all_results)
    pages = max(1, math.ceil(total / per_page))
    offset = (page - 1) * per_page
    page_results = all_results[offset : offset + per_page]
    return {
        "category": category,
        "query": q,
        "words": page_results,
        "total": total,
        "page": page,
        "pages": pages,
        "structured": False,
    }


@router.post("/suggestions")
async def post_dictionary_suggestion(body: WordReportIn) -> WordReportOut:
    result = await submit_dictionary_intake(
        word=body.word,
        category=body.category,
        letter=body.starting_letter,
    )
    return WordReportOut.model_validate(result)
