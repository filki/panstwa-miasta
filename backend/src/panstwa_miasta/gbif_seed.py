"""Logika uzupełniania seedów fauna/flora z GBIF (bez importu pygbif w runtime)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .city_name_rules import keep_city_name_for_pl_game

Bucket = Literal["zwierze", "roslina", "skip"]

DEFAULT_KINGDOM_MAP: dict[str, Bucket] = {
    "Animalia": "zwierze",
    "Plantae": "roslina",
    "Fungi": "roslina",
    "Chromista": "roslina",
    "Bacteria": "skip",
    "Archaea": "skip",
    "Viruses": "skip",
    "Protozoa": "skip",
}

DEFAULT_ACCEPTED_RANKS: frozenset[str] = frozenset({"SPECIES", "SUBSPECIES"})

POLISH_VERNACULAR_LANGS: frozenset[str] = frozenset({"pl", "pol"})

# Litery typowo polskie (ISO 639-3 ``pol``); przy pustym ``language`` w GBIF.
_POLISH_DIACRITICS: frozenset[str] = frozenset("ąćęłńóśźż")


def norm_game(s: str) -> str:
    """Jak ``manager.normalize_text`` / ``seed_scrape_common.norm_game``."""
    text = s.strip().lower().replace("-", " ")
    while "  " in text:
        text = text.replace("  ", " ")
    return text


def keep_fauna_flora_name(nazwa: str) -> bool:
    """Czy nazwa nadaje się do słownika gry (polskie litery + dozwolone znaki)."""
    return keep_city_name_for_pl_game(nazwa)


def vernacular_record_is_polish(record: dict) -> bool:
    """Czy wpis z ``/species/{key}/vernacularNames`` traktujemy jako polski."""
    lang = str(record.get("language") or "").lower()
    if lang in POLISH_VERNACULAR_LANGS:
        return True
    if lang:
        return False
    name = str(record.get("vernacularName") or "")
    return any(ch in _POLISH_DIACRITICS for ch in name)


def polish_vernacular_names(records: list[dict]) -> list[str]:
    """Unikalne polskie nazwy zwyczajowe z listy rekordów GBIF."""
    seen: set[str] = set()
    out: list[str] = []
    for record in records:
        if not vernacular_record_is_polish(record):
            continue
        name = str(record.get("vernacularName") or "").strip()
        if not name or not keep_fauna_flora_name(name):
            continue
        key = norm_game(name)
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def load_kingdom_map(path: Path | None = None) -> dict[str, Bucket]:
    if path is None:
        return dict(DEFAULT_KINGDOM_MAP)
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, Bucket] = {}
    for key, value in raw.items():
        if value not in ("zwierze", "roslina", "skip"):
            msg = f"invalid bucket {value!r} for kingdom {key!r}"
            raise ValueError(msg)
        out[str(key)] = value
    return out


def kingdom_to_bucket(kingdom: str | None, mapping: dict[str, Bucket]) -> Bucket:
    if not kingdom:
        return "skip"
    return mapping.get(kingdom, "skip")


def rank_allowed(rank: str | None, accepted: frozenset[str] = DEFAULT_ACCEPTED_RANKS) -> bool:
    if not rank:
        return False
    return rank.upper() in accepted


@dataclass(frozen=True, slots=True)
class GbifCandidate:
    nazwa_pl: str
    nazwa_norm: str
    kingdom: str
    rank: str
    scientific_name: str
    usage_key: int
    bucket: Bucket


def merge_supplement_norms(
    wiki_norms: set[str],
    gbif_norms: set[str],
    candidate_norms: set[str],
) -> set[str]:
    """Zwraca normy do dopisania do pliku supplement (bez duplikatów wiki ani już w gbif)."""
    existing = wiki_norms | gbif_norms
    return {n for n in candidate_norms if n not in existing}


def split_candidates_by_bucket(
    candidates: list[GbifCandidate],
) -> tuple[set[str], set[str]]:
    animals: set[str] = set()
    plants: set[str] = set()
    for row in candidates:
        if row.bucket == "zwierze":
            animals.add(row.nazwa_norm)
        elif row.bucket == "roslina":
            plants.add(row.nazwa_norm)
    return animals, plants
