"""HTTP API recznej kolejki slownika (bez AI)."""

from __future__ import annotations

import math

import aiosqlite
from fastapi import APIRouter, HTTPException

from ..api_models import WordReportIn, WordReportOut
from ..data import COUNTRIES, JOBS, MIASTA, NAMES, ROSLINY, THINGS, ZWIERZETA
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
    "panstwa": COUNTRIES,
}

# Mapowanie kategorii na tabele SQL z danymi strukturalnymi
STRUCTURED_TABLES = {
    "imiona": {
        "table": "names",
        "columns": "imie AS name, plec AS gender, liczebnosc AS count",
        "where_col": "imie_norm",
        "order": "liczebnosc DESC, imie ASC",
    },
    "panstwa": {
        "table": "countries",
        "columns": "name, continent, capital, population, area_km2, density",
        "where_col": "name_norm",
        "order": "population DESC, name ASC",
    },
    "miasta": {
        "table": "cities",
        "columns": "nazwa AS name, kraj AS country",
        "where_col": "nazwa_norm",
        "order": "nazwa ASC",
    },
}


@router.get("/slownik/{category}/{letter}")
async def get_slownik_words(category: str, letter: str, limit: int = 200):
    """Zwraca slowa dla kategorii + litery z pamieci (ladowanej przy starcie)."""
    words = CAT_MAP.get(category)
    if words is None and category not in STRUCTURED_TABLES:
        raise HTTPException(404, f"Nieznana kategoria: {category}")
    if category in STRUCTURED_TABLES:
        # Dla strukturalnych — deleguj do search
        return await search_slownik(q=letter, category=category, page=1, per_page=limit)
    letter_upper = letter.strip().upper()
    if len(letter_upper) != 1:
        raise HTTPException(400, "Podaj pojedyncza litere")
    filtered = [w for w in words if w.upper().startswith(letter_upper)]
    filtered.sort()
    return {"category": category, "letter": letter_upper, "words": filtered[:limit]}


@router.get("/slownik/categories")
async def get_slownik_categories():
    """Zwraca liste kategorii z liczba slow."""
    counts = {
        "miasta": len(MIASTA),
        "rosliny": len(ROSLINY),
        "zwierzeta": len(ZWIERZETA),
        "zawody": len(JOBS),
        "imiona": len(NAMES),
        "rzeczy": len(THINGS),
        "panstwa": len(COUNTRIES),
    }
    # Dla kategorii strukturalnych dolicz z DB
    async with aiosqlite.connect(_db_path()) as db:
        for cat, info in STRUCTURED_TABLES.items():
            async with db.execute(f"SELECT COUNT(*) as cnt FROM {info['table']}") as cur:
                row = await cur.fetchone()
                counts[cat] = row["cnt"] if row else counts.get(cat, 0)
    return counts


@router.get("/slownik/search")
async def search_slownik(
    q: str = "",
    category: str = "rosliny",
    page: int = 1,
    per_page: int = 10,
):
    """Wyszukiwarka słownikowa z paginacją.

    Kategorie strukturalne (imiona, panstwa, miasta) zwracają dane z SQLite.
    Pozostałe — listę słów z pamięci.
    """
    page = max(1, page)
    per_page = max(1, min(50, per_page))
    q = q.strip().lower()

    # --- Kategorie strukturalne: zapytanie do SQLite ---
    if category in STRUCTURED_TABLES:
        info = STRUCTURED_TABLES[category]
        async with aiosqlite.connect(_db_path()) as db:
            db.row_factory = aiosqlite.Row
            where = ""
            params: list[str] = []
            if q:
                where = f"WHERE {info['where_col']} LIKE ?"
                params = [q + "%"]
            # count
            async with db.execute(
                f"SELECT COUNT(*) as cnt FROM {info['table']} {where}", params
            ) as cur:
                cnt_row = await cur.fetchone()
                total = cnt_row["cnt"] if cnt_row else 0
            # data
            offset = (page - 1) * per_page
            async with db.execute(
                f"SELECT {info['columns']} FROM {info['table']} {where} ORDER BY {info['order']} LIMIT ? OFFSET ?",
                params + [per_page, offset],
            ) as cur:
                rows = await cur.fetchall()
            words = [dict(r) for r in rows]
        pages = max(1, math.ceil(total / per_page))
        return {
            "category": category,
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
