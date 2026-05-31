"""Pre-renderer for /slownik — generates hidden HTML sections + JSON-LD Dataset.

Variant C approach: single URL, all words embedded in HTML for Googlebot,
client-side JS for interactive search.
"""

from __future__ import annotations

from html import escape

import aiosqlite

from panstwa_miasta.data import fold_polish_diacritics

# Polish alphabet — wszystkie litery, nawet te bez słów w danej kategorii
LETTERS = "ABCDEFGHIJKLMNOPRSTUWZ"

# Konfiguracja kategorii: (id, nazwa, ikona, czy_structured, max_preview)
CATEGORIES = [
    ("miasta", "Miasta", "🏙️", True, 20),
    ("panstwa", "Państwa", "🌍", True, 20),
    ("rosliny", "Rośliny", "🌿", False, 20),
    ("zwierzeta", "Zwierzęta", "🐾", True, 20),
    ("imiona", "Imiona", "👤", True, 20),
    ("zawody", "Zawody", "💼", False, 20),
    ("rzeczy", "Rzeczy", "📦", False, 20),
]

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
    "zwierzeta": {
        "table": "animals",
        "columns": "nazwa AS name, nazwa_lacinska AS latin, rodzina AS family, rodzaj AS genus",
        "where_col": "nazwa_norm",
        "order": "nazwa ASC",
    },
}

CATEGORY_DESCRIPTIONS = {
    "miasta": "Miasta to jedna z najbogatszych kategorii — w bazie znajduje się ponad 32 tysiące miejscowości z Polski i świata, od małych wsi po wielkie metropolie. Wystarczy, że nazwa zaczyna się na wylosowaną literę.",
    "panstwa": "Państwa to 205 krajów i terytoriów z całego świata. Dla każdego znajdziesz kontynent, stolicę, populację i powierzchnię.",
    "rosliny": "Rośliny obejmują kwiaty, drzewa, krzewy, owoce, warzywa, zioła i grzyby. Baza zawiera około 19 tysięcy haseł — od popularnych gatunków po egzotyczne okazy.",
    "zwierzeta": "Zwierzęta to ssaki, ptaki, gady, płazy, ryby i owady. W słowniku znajdziesz około 10 tysięcy gatunków, od domowych pupili po dzikie zwierzęta z całego świata.",
    "zawody": "Zawody to profesje i role społeczne — od tradycyjnych rzemieślników po nowoczesne specjalizacje. Kategoria zawiera kilkaset haseł, które wystarczą na wiele rund.",
    "imiona": "Imiona to kategoria, w której liczy się kreatywność — możesz podać dowolne imię żeńskie, męskie lub zdrobnienie. Baza zawiera popularne i rzadkie imiona z różnych krajów.",
    "rzeczy": "Rzeczy to najszersza kategoria — wszystko, co nas otacza: przedmioty codziennego użytku, narzędzia, ubrania, meble, elektronika i wiele więcej. Ponad 5 tysięcy haseł czeka na odkrycie.",
}

SITE_ORIGIN = "https://panstwamiasta.com.pl"

# Kolumny tabel dla kategorii strukturalnych — zgodne z JS TABLE_COLUMNS
_STRUCTURED_HDRS: dict[str, list[tuple[str, str]]] = {
    "miasta": [("name", "Miasto"), ("country", "Kraj")],
    "panstwa": [
        ("name", "Państwo"),
        ("continent", "Kontynent"),
        ("capital", "Stolica"),
    ],
    "imiona": [("name", "Imię"), ("gender", "Płeć"), ("count", "Liczba")],
    "zwierzeta": [
        ("name", "Zwierzę"),
        ("latin", "Nazwa łacińska"),
        ("family", "Rodzina"),
        ("genus", "Rodzaj"),
    ],
}


def _words_by_letter(words: set[str], letter: str) -> list[str]:
    """Zwraca slowa z setu zaczynajace sie na litere (fold diacritics, sorted)."""
    return sorted(w for w in words if fold_polish_diacritics(w).startswith(letter.lower()))


async def _query_structured_by_letter(
    db: aiosqlite.Connection,
    category: str,
    letter: str,
    limit: int = 50,
) -> list[dict]:
    """Query SQLite for structured category words starting with letter."""
    info = STRUCTURED_TABLES.get(category)
    if not info:
        return []
    pattern = f"{letter.lower()}%"
    query = (
        f"SELECT {info['columns']} FROM {info['table']} "
        f"WHERE {info['where_col']} LIKE ? "
        f"ORDER BY {info['order']} LIMIT ?"
    )
    db.row_factory = aiosqlite.Row  # type: ignore[attr-defined]
    async with db.execute(query, [pattern, limit]) as cur:
        rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def _query_structured_counts(
    db: aiosqlite.Connection,
) -> dict[str, int]:
    """Get total word counts for structured categories."""
    counts: dict[str, int] = {}
    for cat, info in STRUCTURED_TABLES.items():
        async with db.execute(f"SELECT COUNT(*) as cnt FROM {info['table']}") as cur:
            row = await cur.fetchone()
            counts[cat] = row["cnt"] if row else 0  # type: ignore[arg-type]
    return counts


def _render_table(
    words: list[dict],
    cat_id: str,
) -> str:
    """Render structured category words as an HTML table."""
    cols = _STRUCTURED_HDRS.get(cat_id, [])
    if not cols:
        return ""

    hdrs = "".join(f"<th>{_escape(label)}</th>" for _, label in cols)
    rows_html = ""
    for w in words:
        cells = "".join("<td>" + _escape(str(w.get(key, ""))) + "</td>" for key, _ in cols)
        rows_html += f"<tr>{cells}</tr>"

    return (
        '<div class="slownik-table-wrap">'
        '<table class="slownik-table">'
        f"<thead><tr>{hdrs}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        "</table>"
        "</div>"
    )


def _render_list(words: list[str]) -> str:
    """Render non-structured words as an inline ul/li."""
    items = "".join(f"<li>{_escape(w)}</li>" for w in words)
    return f'<ul class="word-list">{items}</ul>'


def _escape(s: str) -> str:
    return escape(s)


def _jsonld_itemlist(
    cat_id: str,
    cat_name: str,
    letter: str,
    words: list[str],
) -> dict:
    """Build a JSON-LD ItemList entry for one category×letter."""
    return {
        "@type": "ItemList",
        "name": f"{cat_name} na {letter}",
        "url": f"{SITE_ORIGIN}/slownik#{cat_id}/{letter.lower()}",
        "itemListElement": [{"@type": "Thing", "name": w} for w in words],
    }


async def render_slownik_sections(
    db: aiosqlite.Connection,
    non_structured: dict[str, set[str]],
) -> tuple[str, str, str, dict[str, int]]:
    """Generate pre-rendered content for /slownik.

    Returns:
        (html_sections, json_ld_markup, json_data_markup, category_counts)

    * html_sections — hidden <section> blocks with word previews for Googlebot
    * json_ld_markup — <script type="application/ld+json"> with Dataset
    * json_data_markup — <script id="slownik-data"> with JSON for client JS
    * category_counts — dict of {category_id: word_count}
    """
    sections: list[str] = []
    all_itemlists: list[dict] = []
    client_data: dict[str, dict[str, list]] = {}
    category_counts: dict[str, int] = {}

    # Get structured counts
    structured_counts = await _query_structured_counts(db)

    # Count non-structured
    for cat_id, _cat_name, _icon2, structured, _preview_limit2 in CATEGORIES:
        if structured:
            total = structured_counts.get(cat_id, 0)
        else:
            total = len(non_structured.get(cat_id, set()))
        category_counts[cat_id] = total

    # Render per category×letter
    for cat_id, cat_name, _icon, structured, preview_limit in CATEGORIES:
        letter_data: dict[str, list] = {}

        for letter in LETTERS:
            if structured:
                # Structured — query SQLite, keep full rows for table render
                rows = await _query_structured_by_letter(db, cat_id, letter, limit=preview_limit)
                words_preview = [r["name"] for r in rows]
                letter_data[letter.lower()] = words_preview
                words_html = _render_table(rows, cat_id) if rows else None
            else:
                # Non-structured — filter in-memory set
                words_set = non_structured.get(cat_id, set())
                all_words = _words_by_letter(words_set, letter)
                words_preview = all_words[:preview_limit]
                letter_data[letter.lower()] = words_preview
                words_html = _render_list(words_preview) if words_preview else None

            if not words_html:
                continue

            # Hidden HTML section
            section_id = f"dict-{cat_id}-{letter.lower()}"
            html = (
                f'<section id="{section_id}" hidden>'
                f"<h2>{_escape(cat_name)} na {_escape(letter)}</h2>"
                f"{words_html}"
                f"</section>"
            )
            sections.append(html)

            # JSON-LD ItemList
            all_itemlists.append(_jsonld_itemlist(cat_id, cat_name, letter, words_preview))

        client_data[cat_id] = letter_data

    # Build JSON-LD Dataset
    jsonld = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": "Słownik Państwa-Miasta",
        "description": (
            "Tysiące słów do gry Państwa-Miasta w 7 kategoriach — "
            "miasta, państwa, rośliny, zwierzęta, imiona, zawody, rzeczy."
        ),
        "url": f"{SITE_ORIGIN}/slownik",
        "inLanguage": "pl",
        "hasPart": all_itemlists,
    }
    json_ld_markup = f'<script type="application/ld+json">\n{_compact_json(jsonld)}\n</script>'

    # Client-side data blob (letter → words map per category)
    json_data_markup = (
        f'<script id="slownik-data" type="application/json">\n'
        f"{_compact_json(client_data)}\n"
        f"</script>"
    )

    sections_html = "\n".join(sections)
    return sections_html, json_ld_markup, json_data_markup, category_counts


def _compact_json(obj: object) -> str:
    """Compact JSON without spaces (minified)."""
    import json

    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
