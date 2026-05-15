"""Runtime dictionaries used for answer validation.

Source of truth:

* ``COUNTRIES``  -> SQL table ``countries`` (seeded from
  :mod:`panstwa_miasta.countries_seed`). The set below is just an in-memory
  cache populated by :func:`reload_countries` after the database is
  initialised. Importing this module before :func:`db.init_db` runs is fine
  -- ``COUNTRIES`` will simply be empty until the first reload.
* ``NAMES``      -> SQL table ``names`` (seeded from :mod:`panstwa_miasta.names_seed`).
* ``JOBS``       -> SQL table ``jobs`` (seeded from :mod:`panstwa_miasta.jobs_seed`).
  Regeneracja modułu seed: ``uv run python scripts/build_jobs_seed.py --zawody … --liniowy …``.
  Walidacja w grze: :func:`job_answer_accepted` — m.in. złożenia ``technik …``, ``inżynier …`` itd. (PKD).
* ``MIASTA``     -> SQL table ``cities`` (seeded from :mod:`panstwa_miasta.cities_seed`):
  ``nazwa``, ``kraj`` (polska nazwa państwa jak w ``countries``), normy w DB.
  Dodatkowo każda nazwa dostaje odpowiednik **bez polskich znaków** (np. wpis
  „kalińingrad” → można też wpisać „kaliningrad”). Wybrane homonimy są usuwane
  z walidacji (``MIASTA_NORM_BLOCKLIST``).
* ``ZWIERZETA`` / ``ROSLINY`` — tabele ``animal_norms`` / ``plant_norms`` (seed z
  ``scripts/seed_data/*.jsonl.gz``; uzupełnienie GBIF: ``build_fauna_flora_gbif_supplement.py --apply``).
  Pole „Roślina” to szeroka flora (Zielony Ogródek + Atlas + en.wiki).
  Walidacja: dokładne trafienie albo prefiks pierwszego słowa
  (min. 3 znaki), np. „dzięcioł” przy wpisie „dzięcioł duży”.
  Wpisy z synonimami (``figowiec / fikus``) rozbijamy przy ładowaniu na fragmenty,
  żeby działało też samo „fikus” (prefiks do ``fikus benjamina`` itd.).
  Dodatkowo alias **bez polskich znaków** jak przy ``MIASTA`` (np. „jabłoń” → „jablon”).
  ``ZWIERZETA``: ten sam alias ASCII co ``ROSLINY`` + wpisy z ``ZWIERZETA_EXTRA``
  (np. potoczne „źrebak” / „żrebak”, ogólne „koza”).

In-memory caches are filled by the FastAPI lifespan handler (and pytest
fixtures via :func:`db.init_db`).
"""

from __future__ import annotations

COUNTRIES: set[str] = set()
MIASTA: set[str] = set()
NAMES: set[str] = set()
JOBS: set[str] = set()
ZWIERZETA: set[str] = set()
ROSLINY: set[str] = set()
THINGS: set[str] = set()

# Alias: dla wielowyrazowych zawodów dodajemy pierwsze słowo (>3 znaki) jako
# osobny wpis w zbiorze — tak jak wcześniej przy ``zawody.txt``.
JOB_ALIAS_PREFIX_SKIP = frozenset({"akredytowany", "pomocniczy"})

# Zawód: złożenia „{stem} {specjalizacja}” poza pełną listą ``jobs`` (norma jak ``normalize_text``).
# Wybrane tylko typowe przedrostki złożeń zawodowych (PKD/SYS); bez ultra-szerokich (np. pracownik).
JOB_STANDALONE_OR_PREFIX: frozenset[str] = frozenset(
    {
        "analityk",
        "asystent",
        "blacharz",
        "chirurg",
        "doradca",
        "elektryk",
        "fryzjer",
        "inżynier",
        "inspektor",
        "instruktor",
        "kontroler",
        "laborant",
        "lekarz",
        "mechanik",
        "monter",
        "operator",
        "ratownik",
        "specjalista",
        "technik",
        "tokarz",
        "ślusarz",
    }
)

# Potoczne / luki w seedzie z Wikipedii (norma: małe litery jak ``normalize_text``).
ZWIERZETA_EXTRA: frozenset[str] = frozenset({"źrebak", "żrebak", "koza", "małpa"})

# Potoczne / luki w seedzie roślin (Wikipedia/GBIF).
ROSLINY_EXTRA: frozenset[str] = frozenset({"gruszka", "baobab", "iglak"})

# Miasta z bazy (GeoNames itd.), które w polskiej grze brzmią jak typowa odpowiedź
# w innej kategorii — odrzucamy przy walidacji „Miasto”, żeby uniknąć absurdalnych punktów.
MIASTA_NORM_BLOCKLIST: frozenset[str] = frozenset(
    {
        "uran",  # Uran (Indie) vs pierwiastek „uran” (Rzecz)
    }
)

_PL_FOLD_TRANS = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
    }
)


def fold_polish_diacritics(s: str) -> str:
    """Małe litery PL → ASCII (tylko mapowanie znaków, bez NFKD).

    Używane przy aliasach ASCII (``MIASTA``, ``ROSLINY``, ``ZWIERZETA``) oraz przy
    sprawdzaniu litery rundy (np. Ś → S, Ź/Ż → Z).
    """
    return s.translate(_PL_FOLD_TRANS)


def _add_slash_synonym_fragments(bucket: set[str]) -> None:
    """Dopisuje części po ``/`` (np. ``figowiec x / fikus x`` → osobno ``fikus x``)."""
    for n in list(bucket):
        if "/" not in n:
            continue
        for part in n.split("/"):
            p = part.strip()
            if len(p) >= 2:
                bucket.add(p)


async def reload_countries() -> None:
    """Refresh ``COUNTRIES`` from the SQL ``countries`` table.

    Mutates the existing set in place so callers that already hold a
    reference (e.g. ``from panstwa_miasta.data import COUNTRIES``) keep
    seeing the up-to-date view.
    """
    from .db import load_country_norms

    norms = await load_country_norms()
    COUNTRIES.clear()
    COUNTRIES.update(norms)


async def reload_miasta() -> None:
    """Odświeża ``MIASTA`` z kolumny ``cities.nazwa_norm`` + aliasy bez polskich znaków."""
    from .db import load_city_norms

    norms = await load_city_norms()
    MIASTA.clear()
    MIASTA.update(norms)
    for n in norms:
        folded = fold_polish_diacritics(n)
        if folded != n:
            MIASTA.add(folded)
    MIASTA.difference_update(MIASTA_NORM_BLOCKLIST)


async def reload_names() -> None:
    """Refresh ``NAMES`` from the SQL ``names`` table."""
    from .db import load_name_norms

    norms = await load_name_norms()
    NAMES.clear()
    NAMES.update(norms)


async def reload_jobs() -> None:
    """Odświeża ``JOBS`` z tabeli ``jobs`` + aliasy pierwszego słowa."""
    from .db import load_job_norms

    norms = await load_job_norms()
    JOBS.clear()
    for n in norms:
        JOBS.add(n)
        words = n.split()
        if len(words) >= 2:
            head = words[0]
            if len(head) > 3 and head not in JOB_ALIAS_PREFIX_SKIP:
                JOBS.add(head)


async def reload_things() -> None:
    """Odświeża ``THINGS`` z tabeli ``things`` (zaakceptowane odpowiedzi „Rzecz”)."""
    from .db import load_thing_norms

    norms = await load_thing_norms()
    THINGS.clear()
    THINGS.update(norms)


def job_answer_accepted(ans_norm: str) -> bool:
    """Czy odpowiedź w kategorii Zawód jest poprawna (``JOBS`` + :data:`JOB_STANDALONE_OR_PREFIX`)."""
    if ans_norm in JOBS:
        return True
    for stem in JOB_STANDALONE_OR_PREFIX:
        if ans_norm == stem or ans_norm.startswith(f"{stem} "):
            return True
    return False


async def reload_zwierzeta() -> None:
    """Ładuje ``ZWIERZETA`` z tabeli ``animal_norms`` + ``ZWIERZETA_EXTRA`` + aliasy ASCII."""
    from .db import load_animal_norms

    ZWIERZETA.clear()
    ZWIERZETA.update(await load_animal_norms())
    ZWIERZETA.update(ZWIERZETA_EXTRA)
    _add_slash_synonym_fragments(ZWIERZETA)
    for n in list(ZWIERZETA):
        folded = fold_polish_diacritics(n)
        if folded != n:
            ZWIERZETA.add(folded)


async def reload_rosliny() -> None:
    """Ładuje ``ROSLINY`` z tabeli ``plant_norms`` + ``ROSLINY_EXTRA`` + aliasy ASCII."""
    from .db import load_plant_norms

    ROSLINY.clear()
    ROSLINY.update(await load_plant_norms())
    ROSLINY.update(ROSLINY_EXTRA)
    _add_slash_synonym_fragments(ROSLINY)
    for n in list(ROSLINY):
        folded = fold_polish_diacritics(n)
        if folded != n:
            ROSLINY.add(folded)
