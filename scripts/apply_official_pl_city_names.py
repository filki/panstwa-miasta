#!/usr/bin/env python3
"""Uzupełnia ``scripts/seed_data/cities_geonames.jsonl.gz`` z ``data/miasta_oficjalne_pl.csv``.

Dla każdego wiersza CSV (GeoNames + ``nazwa_polska``):
- jeśli w seedzie jest miasto o tej samej nazwie angielskiej (``name``) i kraju → zamień na ``nazwa_polska``;
- jeśli brakuje pary (``nazwa_polska``, kraj) → dodaj.

Polska (PL) pomijana — ``cities_seed_pl_generated`` (Wikidata).

Uruchom z katalogu głównego repozytorium::

    uv run python scripts/apply_official_pl_city_names.py
    uv run python scripts/apply_official_pl_city_names.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_cities_from_geonames import (  # noqa: E402
    _iso_to_kraj,
    _looks_like_short_all_caps_code,
    _norm_key,
)

from panstwa_miasta.city_name_rules import keep_city_name_for_geonames_seed  # noqa: E402
from panstwa_miasta.countries_seed import COUNTRIES_SEED  # noqa: E402
from panstwa_miasta.seed_data_loader import (  # noqa: E402
    load_cities_geonames_from_seed_file,
    seed_data_path,
    write_cities_geonames_jsonl_gz,
)


def _load_csv_rows(
    csv_path: Path,
    country_json: Path,
    min_pop: int,
) -> list[tuple[str, str, str]]:
    """(nazwa_polska, kraj, name_geonames) — tylko wiersze zmapowane do ``countries_seed``."""
    seed_names = frozenset(c["name"] for c in COUNTRIES_SEED)
    iso_pl = json.loads(country_json.read_text(encoding="utf-8"))
    out: list[tuple[str, str, str]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            iso = row["country_code"].strip()
            if iso == "PL":
                continue
            try:
                pop = int(row["population"])
            except ValueError:
                continue
            if pop < min_pop:
                continue
            kraj = _iso_to_kraj(iso, "", seed_names, iso_pl)
            if not kraj:
                continue
            en = row["name"].strip()
            pol = row["nazwa_polska"].strip()
            if not pol or not en:
                continue
            if _looks_like_short_all_caps_code(pol) or _looks_like_short_all_caps_code(en):
                continue
            if not keep_city_name_for_geonames_seed(pol):
                continue
            out.append((pol, kraj, en))
    return out


def apply_csv_to_seed(
    existing: list[tuple[str, str]],
    csv_rows: list[tuple[str, str, str]],
) -> tuple[list[tuple[str, str]], dict[str, int]]:
    """Zwraca posortowaną listę i statystyki."""
    by_key: dict[tuple[str, str], tuple[str, str]] = {}
    for nazwa, kraj in existing:
        by_key[(_norm_key(nazwa), _norm_key(kraj))] = (nazwa, kraj)

    stats = {"renamed": 0, "added": 0, "unchanged": 0, "merged_duplicate": 0}

    for pol, kraj, en in csv_rows:
        key_en = (_norm_key(en), _norm_key(kraj))
        key_pol = (_norm_key(pol), _norm_key(kraj))

        if key_en in by_key:
            old_nazwa, old_kraj = by_key[key_en]
            if old_nazwa == pol and old_kraj == kraj:
                stats["unchanged"] += 1
            else:
                del by_key[key_en]
                if key_pol in by_key and key_pol != key_en:
                    stats["merged_duplicate"] += 1
                else:
                    stats["renamed"] += 1
                by_key[key_pol] = (pol, kraj)
        elif key_pol in by_key:
            stats["unchanged"] += 1
        else:
            by_key[key_pol] = (pol, kraj)
            stats["added"] += 1

    rows = sorted(by_key.values(), key=lambda r: (r[1].lower(), r[0].lower()))
    return rows, stats


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Apply data/miasta_oficjalne_pl.csv to GeoNames city seed (jsonl.gz)"
    )
    ap.add_argument(
        "--csv",
        type=Path,
        default=REPO_ROOT / "data" / "miasta_oficjalne_pl.csv",
    )
    ap.add_argument(
        "--country-json",
        type=Path,
        default=REPO_ROOT / "scripts" / "data" / "country_iso_pl_umpirsky.json",
    )
    ap.add_argument(
        "--seed",
        type=Path,
        default=seed_data_path("cities_geonames.jsonl.gz"),
    )
    ap.add_argument("--min-pop", type=int, default=15000)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    existing = load_cities_geonames_from_seed_file()

    csv_rows = _load_csv_rows(args.csv, args.country_json, args.min_pop)
    updated, stats = apply_csv_to_seed(existing, csv_rows)

    print(f"Existing rows: {len(existing)}")
    print(f"CSV mapped rows: {len(csv_rows)}")
    print(f"Result rows: {len(updated)}")
    print("Stats:", stats)

    samples = [
        ("London", "Wielka Brytania", "Londyn"),
        ("Moscow", "Rosja", "Moskwa"),
        ("Paris", "Francja", "Paryż"),
        ("Rome", "Włochy", "Rzym"),
        ("Cologne", "Niemcy", "Kolonia"),
    ]
    by_pair = {(n, k) for n, k in updated}
    print("\nSample checks:")
    for en, kraj, expected in samples:
        ok = (expected, kraj) in by_pair
        bad = (en, kraj) in by_pair
        print(f"  {expected} ({kraj}): {'OK' if ok else 'MISSING'}", end="")
        if bad:
            print(f" — still has {en!r}", end="")
        print()

    if args.dry_run:
        print("\n(dry-run: seed file not written)")
        return

    n = write_cities_geonames_jsonl_gz(updated)
    print(f"\nWrote {n} rows → {args.seed}")


if __name__ == "__main__":
    main()
