"""Reguły nazw miast pod grę po polsku (spójne z seedami z Wikipedii / Wikidata)."""

from __future__ import annotations

import unicodedata

# Litery polskiego alfabetu (małe i wielkie).
POLISH_ALPHABET: frozenset[str] = frozenset(
    "aąbcćdeęfghijklłmnńoóprsśtuwyzźżAĄBCĆDEĘFGHIJKLŁMNŃOÓPRSŚTUWYZŹŻ"
)

# Dozwolone znaki nieliterowe w nazwie (spacja, myślnik, apostrofy, interpunkcja, cyfry).
CITY_NAME_ALLOWED_NON_LETTERS: frozenset[str] = frozenset(" '-.'’(),0123456789")

# Litery łacińskie częste w zapisach obcych nazw (GeoNames); tylko import seedów świata.
FOREIGN_GEO_NAME_EXTRA_LATIN: frozenset[str] = frozenset("vqVxQX")


def keep_city_name_for_pl_game(nazwa: str) -> bool:
    """Czy nazwa składa się wyłącznie z liter PL + ``CITY_NAME_ALLOWED_NON_LETTERS`` i ma co najmniej jedną literę PL."""
    s = unicodedata.normalize("NFC", nazwa.strip().replace("\u00a0", " "))
    if not s:
        return False
    if not any(ch in POLISH_ALPHABET for ch in s):
        return False
    for ch in s:
        if ch in POLISH_ALPHABET or ch in CITY_NAME_ALLOWED_NON_LETTERS:
            continue
        return False
    return True


def keep_city_name_for_geonames_seed(nazwa: str) -> bool:
    """Jak ``keep_city_name_for_pl_game``, ale dopuszcza ``vqVxQX`` (obce nazwy z GeoNames)."""
    s = unicodedata.normalize("NFC", nazwa.strip().replace("\u00a0", " "))
    if not s:
        return False
    letters = POLISH_ALPHABET | FOREIGN_GEO_NAME_EXTRA_LATIN
    if not any(ch in POLISH_ALPHABET for ch in s):
        return False
    for ch in s:
        if ch in letters or ch in CITY_NAME_ALLOWED_NON_LETTERS:
            continue
        return False
    return True
