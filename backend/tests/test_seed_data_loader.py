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


def test_iter_jsonl_gz_missing_file(tmp_path):
    """iter_jsonl_gz returns empty iterator for non-existent file."""
    from panstwa_miasta.seed_data_loader import iter_jsonl_gz

    missing = tmp_path / "nonexistent.jsonl.gz"
    rows = list(iter_jsonl_gz(missing))
    assert rows == []


def test_write_animal_norms_roundtrip(tmp_path, monkeypatch):
    from panstwa_miasta.seed_data_loader import (
        _SEED_DATA_DIR,
        iter_animal_norms_from_seed_file,
        write_animal_norms_jsonl_gz,
    )

    out_dir = tmp_path / "seed_data"
    monkeypatch.setattr("panstwa_miasta.seed_data_loader._SEED_DATA_DIR", out_dir)

    norms: set[str] = {"jeleń szlachetny", "sarna europejska", "lis rudy"}
    count = write_animal_norms_jsonl_gz(norms)
    assert count == 3

    result = list(iter_animal_norms_from_seed_file())
    assert sorted(result) == sorted(norms)


def test_write_plant_norms_roundtrip(tmp_path, monkeypatch):
    from panstwa_miasta.seed_data_loader import (
        _SEED_DATA_DIR,
        iter_plant_norms_from_seed_file,
        write_plant_norms_jsonl_gz,
    )

    out_dir = tmp_path / "seed_data"
    monkeypatch.setattr("panstwa_miasta.seed_data_loader._SEED_DATA_DIR", out_dir)

    norms: set[str] = {"pokrzywa zwyczajna", "mniszek lekarski"}
    count = write_plant_norms_jsonl_gz(norms)
    assert count == 2

    result = list(iter_plant_norms_from_seed_file())
    assert sorted(result) == sorted(norms)


def test_write_cities_geonames_roundtrip(tmp_path, monkeypatch):
    from panstwa_miasta.seed_data_loader import (
        _SEED_DATA_DIR,
        seed_data_path,
        write_cities_geonames_jsonl_gz,
        write_jsonl_gz,
    )

    out_dir = tmp_path / "seed_data"
    monkeypatch.setattr("panstwa_miasta.seed_data_loader._SEED_DATA_DIR", out_dir)

    rows: list[tuple[str, str]] = [("Gniezno", "Polska"), ("Paryż", "Francja")]
    count = write_cities_geonames_jsonl_gz(rows)
    assert count == 2

    # Read back manually
    from panstwa_miasta.seed_data_loader import iter_jsonl_gz

    result = list(iter_jsonl_gz(seed_data_path("cities_geonames.jsonl.gz")))
    assert len(result) == 2
    assert result[0]["nazwa"] == "Gniezno"
    assert result[1]["kraj"] == "Francja"
