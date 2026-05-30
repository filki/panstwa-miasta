"""Ładowanie słowników z ``scripts/seed_data/*.jsonl.gz`` (zamiast wielkich modułów ``*_generated.py``)."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

_SEED_DATA_DIR = Path(__file__).resolve().parents[2] / "scripts" / "seed_data"


def seed_data_path(name: str) -> Path:
    return _SEED_DATA_DIR / name


def iter_jsonl_gz(path: Path):
    """Yields dict per line from a gzip JSONL file."""
    if not path.is_file():
        return
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def iter_animal_norms_from_seed_file():
    for row in iter_jsonl_gz(seed_data_path("animals_norms.jsonl.gz")):
        yield row["norm"]


def iter_plant_norms_from_seed_file():
    for row in iter_jsonl_gz(seed_data_path("plants_norms.jsonl.gz")):
        yield row["norm"]


def load_animal_norms_from_seed_file() -> list[str]:
    return list(iter_animal_norms_from_seed_file())


def load_plant_norms_from_seed_file() -> list[str]:
    return list(iter_plant_norms_from_seed_file())


def load_cities_geonames_from_seed_file() -> list[tuple[str, str]]:
    return [
        (row["nazwa"], row["kraj"])
        for row in iter_jsonl_gz(seed_data_path("cities_geonames.jsonl.gz"))
    ]


def load_cities_polonized_from_seed_file() -> list[tuple[str, str]]:
    return [
        (row["nazwa"], row["kraj"])
        for row in iter_jsonl_gz(seed_data_path("cities_polonized.jsonl.gz"))
    ]


def load_cities_to_translate_from_seed_file() -> list[tuple[str, str]]:
    return [
        (row["nazwa"], row["kraj"])
        for row in iter_jsonl_gz(seed_data_path("cities_to_translate.jsonl.gz"))
    ]


def write_jsonl_gz(path: Path, rows: list[dict[str, str]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def write_animal_norms_jsonl_gz(norms: set[str] | frozenset[str]) -> int:
    items = sorted(norms)
    return write_jsonl_gz(
        seed_data_path("animals_norms.jsonl.gz"),
        [{"norm": n} for n in items],
    )


def write_plant_norms_jsonl_gz(norms: set[str] | frozenset[str]) -> int:
    items = sorted(norms)
    return write_jsonl_gz(
        seed_data_path("plants_norms.jsonl.gz"),
        [{"norm": n} for n in items],
    )


def write_cities_geonames_jsonl_gz(rows: list[tuple[str, str]]) -> int:
    return write_jsonl_gz(
        seed_data_path("cities_geonames.jsonl.gz"),
        [{"nazwa": nazwa, "kraj": kraj} for nazwa, kraj in rows],
    )
