"""Mapowanie obcych zapisów odpowiedzi geo na polskie normy ze słownika gry.

Walidacja Państwo/Miasto: najpierw alias (np. ``stockholm`` → ``sztokholm``),
potem uproszczenie zapisu niemieckiego (``ü`` → ``u``, ``ß`` → ``ss``).
W bazie zostają wyłącznie polskie nazwy — nie dopisujemy angielskich exonimów do seedów.
"""

from __future__ import annotations

_DE_GEO_FOLD_TRANS = str.maketrans(
    {
        "ä": "a",
        "ö": "o",
        "ü": "u",
        "ß": "ss",
    }
)

_NORM_SOUTH_AFRICA = "południowa afryka"
_NORM_UNITED_STATES = "stany zjednoczone"

# Obcy zapis (norma) → polska norma już w ``MIASTA`` / ``COUNTRIES``.
CITY_ANSWER_ALIASES: dict[str, str] = {
    "stockholm": "sztokholm",
    "cologne": "kolonia",
    "koeln": "kolonia",
    "koln": "kolonia",
    "munich": "monachium",
    "munchen": "monachium",
    "muenchen": "monachium",
    "vienna": "wiedeń",
    "wien": "wiedeń",
    "nuremberg": "norymberga",
    "nurnberg": "norymberga",
    "nuernberg": "norymberga",
    "zurich": "zurych",
    "geneva": "genewa",
    "genf": "genewa",
    "brussels": "bruksela",
    "bruxelles": "bruksela",
    "copenhagen": "kopenhaga",
    "kobenhavn": "kopenhaga",
    "prague": "praga",
    "prahy": "praga",
    "budapest": "budapeszt",
    "athens": "ateny",
    "moscow": "moskwa",
    "moskva": "moskwa",
    "kiev": "kijów",
    "kyiv": "kijów",
    "belgrade": "belgrad",
    "beograd": "belgrad",
    "bucharest": "bukareszt",
    "bucuresti": "bukareszt",
    "jerusalem": "jerozolima",
    "the hague": "haga",
    "den haag": "haga",
}

COUNTRY_ANSWER_ALIASES: dict[str, str] = {
    "rpa": _NORM_SOUTH_AFRICA,
    "republika poludniowej afryki": _NORM_SOUTH_AFRICA,
    "republika południowej afryki": _NORM_SOUTH_AFRICA,
    "south africa": _NORM_SOUTH_AFRICA,
    "vereinigte staaten": _NORM_UNITED_STATES,
    "united states": _NORM_UNITED_STATES,
    "usa": _NORM_UNITED_STATES,
    "united kingdom": "wielka brytania",
    "great britain": "wielka brytania",
    "czech republic": "czechy",
    "north macedonia": "macedonia północna",
}


def fold_german_geo_spelling(s: str) -> str:
    """Niemieckie znaki diakrytyczne i ``ß`` → zapis łaciński (małe litery)."""
    return s.translate(_DE_GEO_FOLD_TRANS)


def resolve_city_answer(ans_norm: str) -> str:
    """Zwraca normę do sprawdzenia w ``MIASTA``."""
    folded = fold_german_geo_spelling(ans_norm)
    for candidate in (ans_norm, folded):
        if candidate in CITY_ANSWER_ALIASES:
            return CITY_ANSWER_ALIASES[candidate]
    return folded


def resolve_country_answer(ans_norm: str) -> str:
    """Zwraca normę do sprawdzenia w ``COUNTRIES``."""
    folded = fold_german_geo_spelling(ans_norm)
    for candidate in (ans_norm, folded):
        if candidate in COUNTRY_ANSWER_ALIASES:
            return COUNTRY_ANSWER_ALIASES[candidate]
    return folded
