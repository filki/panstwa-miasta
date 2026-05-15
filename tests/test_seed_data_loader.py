"""Tests for scripts/seed_data JSONL.gz loaders."""

from panstwa_miasta.seed_data_loader import (
    load_animal_norms_from_seed_file,
    load_cities_geonames_from_seed_file,
    load_plant_norms_from_seed_file,
    seed_data_path,
)


def test_seed_data_files_exist():
    assert seed_data_path("animals_norms.jsonl.gz").is_file()
    assert seed_data_path("plants_norms.jsonl.gz").is_file()
    assert seed_data_path("cities_geonames.jsonl.gz").is_file()


def test_load_animal_norms_non_empty():
    norms = load_animal_norms_from_seed_file()
    assert len(norms) > 1000
    assert all(isinstance(n, str) and n for n in norms[:5])


def test_load_plant_norms_non_empty():
    norms = load_plant_norms_from_seed_file()
    assert len(norms) > 1000


def test_load_cities_geonames_has_londyn():
    rows = load_cities_geonames_from_seed_file()
    assert len(rows) > 10_000
    assert ("Londyn", "Wielka Brytania") in rows
