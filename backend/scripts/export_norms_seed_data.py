#!/usr/bin/env python3
"""Eksport / scalanie norm do ``scripts/seed_data/*.jsonl.gz``.

Po przebudowie wiki lub GeoNames uruchom ponownie, aby zaktualizować pliki w repo.

    uv run python scripts/export_norms_seed_data.py --merge-gbif-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from panstwa_miasta.seed_data_loader import (  # noqa: E402
    load_animal_norms_from_seed_file,
    load_cities_geonames_from_seed_file,
    load_plant_norms_from_seed_file,
    write_animal_norms_jsonl_gz,
    write_cities_geonames_jsonl_gz,
    write_plant_norms_jsonl_gz,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    animals = load_animal_norms_from_seed_file()
    plants = load_plant_norms_from_seed_file()
    cities = load_cities_geonames_from_seed_file()

    na = write_animal_norms_jsonl_gz(set(animals))
    np = write_plant_norms_jsonl_gz(set(plants))
    nc = write_cities_geonames_jsonl_gz(cities)

    print(f"animals_norms: {na} norms")
    print(f"plants_norms: {np} norms")
    print(f"cities_geonames: {nc} rows")


if __name__ == "__main__":
    main()
