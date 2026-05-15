#!/usr/bin/env python3
"""Uzupełnia seedy fauna/flora polskimi nazwami zwyczajowymi z GBIF.

Dla każdej normy z wiki seedów: ``species/search?q=…``, potem
``species/{key}/vernacularNames`` (język ``pol`` / ``pl`` lub polskie znaki).
Paginacja ``species/search?language=pol`` nie zwraca ``vernacularName`` — nie używamy.

    uv sync --extra gbif
    uv run python scripts/build_fauna_flora_gbif_supplement.py --max-seeds 500 --dry-run
    uv run python scripts/build_fauna_flora_gbif_supplement.py --apply

``--apply`` dopisuje tylko normy spoza wiki seed i dotychczasowego supplement.
Dane GBIF: https://www.gbif.org/terms
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from seed_scrape_common import polite_sleep  # noqa: E402

from panstwa_miasta.gbif_seed import (  # noqa: E402
    DEFAULT_ACCEPTED_RANKS,
    GbifCandidate,
    keep_fauna_flora_name,
    kingdom_to_bucket,
    load_kingdom_map,
    merge_supplement_norms,
    norm_game,
    polish_vernacular_names,
    rank_allowed,
    split_candidates_by_bucket,
)
from panstwa_miasta.seed_data_loader import (  # noqa: E402
    load_animal_norms_from_seed_file,
    load_plant_norms_from_seed_file,
    write_animal_norms_jsonl_gz,
    write_plant_norms_jsonl_gz,
)

GBIF_API = "https://api.gbif.org/v1"
UA = "PanstwaMiasta/1.0 (+https://github.com/filki/panstwa-miasta; GBIF fauna/flora seed)"
SEARCH_LIMIT = 8
VERNACULAR_LIMIT = 500


def _wiki_seed_norms() -> list[str]:
    merged = sorted(
        set(load_animal_norms_from_seed_file()) | set(load_plant_norms_from_seed_file())
    )
    return merged


def _get_json(client: httpx.Client, url: str, *, params: dict | None = None) -> dict:
    for attempt in range(5):
        resp = client.get(url, params=params)
        if resp.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        return resp.json()
    msg = f"GBIF request failed after retries: {url}"
    raise RuntimeError(msg)


def _search_by_vernacular(client: httpx.Client, norm: str) -> list[dict]:
    data = _get_json(
        client,
        f"{GBIF_API}/species/search",
        params={"q": norm, "limit": SEARCH_LIMIT, "status": "ACCEPTED"},
    )
    return list(data.get("results") or [])


def _vernacular_records(
    client: httpx.Client,
    usage_key: int,
    cache: dict[int, list[dict]],
) -> list[dict]:
    if usage_key in cache:
        return cache[usage_key]
    data = _get_json(
        client,
        f"{GBIF_API}/species/{usage_key}/vernacularNames",
        params={"limit": VERNACULAR_LIMIT},
    )
    records = list(data.get("results") or [])
    cache[usage_key] = records
    polite_sleep(0.12)
    return records


def _resolve_kingdom_rank(
    row: dict,
    backbone_cache: dict[int, dict],
) -> tuple[str | None, str | None]:
    kingdom = row.get("kingdom")
    rank = row.get("rank")
    if kingdom and rank:
        return kingdom, rank
    key = row.get("key") or row.get("acceptedKey")
    if key is None:
        return kingdom, rank
    usage_key = int(key)
    if usage_key not in backbone_cache:
        try:
            from pygbif import species as gbif_species

            backbone_cache[usage_key] = gbif_species.name_backbone(key=usage_key)
        except Exception:
            backbone_cache[usage_key] = {}
        polite_sleep(0.15)
    bb = backbone_cache[usage_key]
    return bb.get("kingdom") or kingdom, bb.get("rank") or rank


def _add_candidate(
    out: list[GbifCandidate],
    seen: set[tuple[str, str]],
    *,
    vernacular: str,
    kingdom: str,
    rank: str,
    scientific_name: str,
    usage_key: int,
    bucket: str,
) -> None:
    if not keep_fauna_flora_name(vernacular):
        return
    nazwa_norm = norm_game(vernacular)
    dedupe_key = (nazwa_norm, bucket)
    if dedupe_key in seen:
        return
    seen.add(dedupe_key)
    out.append(
        GbifCandidate(
            nazwa_pl=vernacular,
            nazwa_norm=nazwa_norm,
            kingdom=kingdom,
            rank=rank,
            scientific_name=scientific_name,
            usage_key=usage_key,
            bucket=bucket,  # type: ignore[arg-type]
        )
    )


def collect_candidates(
    *,
    max_seeds: int | None,
    kingdom_map_path: Path,
    include_genus: bool,
    verbose: bool,
) -> list[GbifCandidate]:
    mapping = load_kingdom_map(kingdom_map_path)
    accepted = DEFAULT_ACCEPTED_RANKS | (frozenset({"GENUS"}) if include_genus else frozenset())
    backbone_cache: dict[int, dict] = {}
    vernacular_cache: dict[int, list[dict]] = {}
    seen_norm_bucket: set[tuple[str, str]] = set()
    out: list[GbifCandidate] = []

    seeds = _wiki_seed_norms()
    if max_seeds is not None:
        seeds = seeds[:max_seeds]

    headers = {"User-Agent": UA}
    with httpx.Client(timeout=60.0, headers=headers) as client:
        for idx, norm in enumerate(seeds, start=1):
            if verbose and idx % 100 == 0:
                print(f"  … {idx}/{len(seeds)} seedów, {len(out)} kandydatów")
            try:
                hits = _search_by_vernacular(client, norm)
            except httpx.HTTPError as exc:
                print(f"  pominięto {norm!r}: {exc}")
                polite_sleep(1.0)
                continue

            polite_sleep(0.25)

            for row in hits:
                kingdom, resolved_rank = _resolve_kingdom_rank(row, backbone_cache)
                if not rank_allowed(resolved_rank, accepted):
                    continue
                bucket = kingdom_to_bucket(kingdom, mapping)
                if bucket == "skip":
                    continue
                usage_key = int(row.get("key") or row.get("acceptedKey") or 0)
                if usage_key <= 0:
                    continue
                scientific = str(row.get("scientificName") or "")
                kingdom_s = str(kingdom or "")
                rank_s = str(resolved_rank or "")

                try:
                    vn_records = _vernacular_records(client, usage_key, vernacular_cache)
                except httpx.HTTPError:
                    continue

                for pl_name in polish_vernacular_names(vn_records):
                    _add_candidate(
                        out,
                        seen_norm_bucket,
                        vernacular=pl_name,
                        kingdom=kingdom_s,
                        rank=rank_s,
                        scientific_name=scientific,
                        usage_key=usage_key,
                        bucket=bucket,
                    )

    return out


def write_candidates_csv(path: Path, candidates: list[GbifCandidate]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "nazwa_norm",
                "nazwa_pl",
                "kingdom",
                "rank",
                "scientificName",
                "usageKey",
                "bucket",
            ]
        )
        for row in sorted(candidates, key=lambda r: (r.bucket, r.nazwa_norm)):
            writer.writerow(
                [
                    row.nazwa_norm,
                    row.nazwa_pl,
                    row.kingdom,
                    row.rank,
                    row.scientific_name,
                    row.usage_key,
                    row.bucket,
                ]
            )


def apply_supplements(candidates: list[GbifCandidate]) -> tuple[int, int]:
    wiki_animals = set(load_animal_norms_from_seed_file())
    wiki_plants = set(load_plant_norms_from_seed_file())

    cand_animals, cand_plants = split_candidates_by_bucket(candidates)
    new_animals = merge_supplement_norms(wiki_animals, set(), cand_animals)
    new_plants = merge_supplement_norms(wiki_plants, set(), cand_plants)

    merged_animals = wiki_animals | new_animals
    merged_plants = wiki_plants | new_plants

    write_animal_norms_jsonl_gz(merged_animals)
    write_plant_norms_jsonl_gz(merged_plants)
    return len(new_animals), len(new_plants)


def main() -> None:
    ap = argparse.ArgumentParser(description="GBIF supplement for fauna/flora seeds")
    ap.add_argument(
        "--kingdom-map",
        type=Path,
        default=SCRIPTS_DIR / "data" / "gbif_kingdom_map.json",
    )
    ap.add_argument(
        "--candidates-csv",
        type=Path,
        default=REPO_ROOT / "data" / "gbif_candidates.csv",
    )
    ap.add_argument(
        "--max-seeds",
        type=int,
        default=None,
        help="Limit norm z wiki seedów (PoC); domyślnie wszystkie ~20k",
    )
    ap.add_argument("--include-genus", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total_seeds = len(_wiki_seed_norms())
    limit = args.max_seeds if args.max_seeds is not None else total_seeds
    print(
        f"Pobieranie kandydatów z GBIF (wiki seed → search + vernacularNames, {limit}/{total_seeds})…"
    )
    candidates = collect_candidates(
        max_seeds=args.max_seeds,
        kingdom_map_path=args.kingdom_map,
        include_genus=args.include_genus,
        verbose=args.verbose,
    )
    animals, plants = split_candidates_by_bucket(candidates)
    print(f"Kandydaci: {len(candidates)} (zwierzę: {len(animals)}, roślina: {len(plants)})")

    if args.dry_run:
        for row in candidates[:20]:
            print(
                f"  {row.bucket:8} {row.nazwa_pl:30} "
                f"{row.kingdom}/{row.rank} ({row.scientific_name})"
            )
        print("(dry-run: bez zapisu CSV/supplement)")
        return

    write_candidates_csv(args.candidates_csv, candidates)
    print(f"Zapisano {args.candidates_csv}")

    if args.apply:
        added_a, added_p = apply_supplements(candidates)
        print(f"Supplement: +{added_a} zwierząt, +{added_p} roślin (nowe normy)")


if __name__ == "__main__":
    main()
