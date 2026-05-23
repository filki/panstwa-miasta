"""Testy logiki uzupełnienia GBIF (bez sieci)."""

from __future__ import annotations

from pathlib import Path

from panstwa_miasta.gbif_seed import (
    GbifCandidate,
    kingdom_to_bucket,
    load_kingdom_map,
    merge_supplement_norms,
    norm_game,
    polish_vernacular_names,
    rank_allowed,
    split_candidates_by_bucket,
    vernacular_record_is_polish,
)


def test_vernacular_record_is_polish_iso639_3() -> None:
    assert vernacular_record_is_polish({"vernacularName": "Borowik", "language": "pol"})
    assert not vernacular_record_is_polish({"vernacularName": "Boleti", "language": "ita"})


def test_vernacular_record_is_polish_empty_lang_with_diacritic() -> None:
    assert vernacular_record_is_polish({"vernacularName": "dąb", "language": ""})
    assert not vernacular_record_is_polish({"vernacularName": "oak", "language": ""})


def test_polish_vernacular_names_dedupes() -> None:
    records = [
        {"vernacularName": "Lew", "language": "pol"},
        {"vernacularName": "lew", "language": "pol"},
        {"vernacularName": "Boleti", "language": "ita"},
    ]
    assert polish_vernacular_names(records) == ["Lew"]


def test_kingdom_to_bucket_default_map() -> None:
    mapping = load_kingdom_map()
    assert kingdom_to_bucket("Animalia", mapping) == "zwierze"
    assert kingdom_to_bucket("Plantae", mapping) == "roslina"
    assert kingdom_to_bucket("Fungi", mapping) == "roslina"
    assert kingdom_to_bucket("Bacteria", mapping) == "skip"


def test_kingdom_map_from_json(tmp_path: Path) -> None:
    path = tmp_path / "map.json"
    path.write_text('{"Animalia": "zwierze", "Viruses": "skip"}', encoding="utf-8")
    mapping = load_kingdom_map(path)
    assert kingdom_to_bucket("Viruses", mapping) == "skip"


def test_merge_supplement_skips_wiki_and_existing() -> None:
    wiki = {"lew", "pies"}
    gbif = {"kot"}
    candidates = {"lew", "kot", "sowa"}
    assert merge_supplement_norms(wiki, gbif, candidates) == {"sowa"}


def test_split_candidates_by_bucket() -> None:
    rows = [
        GbifCandidate("Lew", "lew", "Animalia", "SPECIES", "Panthera leo", 1, "zwierze"),
        GbifCandidate("Dąb", "dąb", "Plantae", "SPECIES", "Quercus", 2, "roslina"),
    ]
    animals, plants = split_candidates_by_bucket(rows)
    assert animals == {"lew"}
    assert plants == {"dąb"}


def test_rank_allowed() -> None:
    assert rank_allowed("SPECIES")
    assert rank_allowed("species")
    assert not rank_allowed("GENUS")
    assert rank_allowed("GENUS", frozenset({"GENUS", "SPECIES"}))


def test_norm_game() -> None:
    assert norm_game("  Lew  Afrykański ") == "lew afrykański"
