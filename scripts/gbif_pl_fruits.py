#!/usr/bin/env python3
"""Szuka w GBIF gatunków roślin z polskimi nazwami zwyczajowymi.

Strategia:
1. Bierze rodziny roślin owocowych (Rosaceae, Rutaceae, Cucurbitaceae itd.)
2. Dla KAŻDEJ rodziny pobiera gatunki przez pygbif name_lookup
3. Dla każdego gatunku sprawdza czy ma polskie vernacularName (przez nubKey)
4. Zbiera polskie nazwy → dopisuje do plant_norms

Używa pygbif zamiast raw HTTP.

    uv run python scripts/gbif_pl_fruits.py --dry-run
    uv run python scripts/gbif_pl_fruits.py --apply
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

from pygbif import species

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from panstwa_miasta.gbif_seed import keep_fauna_flora_name, norm_game  # noqa: E402
from panstwa_miasta.seed_data_loader import (  # noqa: E402
    load_plant_norms_from_seed_file,
    write_plant_norms_jsonl_gz,
)

POLISH_CHARS = frozenset("ąćęłńóśźż")

# Rodziny owocowe + ich nubKey w GBIF backbone (datasetKey=d7dddbf4-…)
FAMILY_NUBKEYS: dict[str, int] = {
    "Rosaceae": 5015,  # jabłka, gruszki, śliwki, wiśnie, truskawki, maliny
    "Rutaceae": 5014,  # cytrusy
    "Cucurbitaceae": 4450,  # dynie, ogórki, arbuzy
    "Solanaceae": 4961,  # pomidory, ziemniaki, papryka
    "Ericaceae": 2503,  # borówki, żurawiny
    "Grossulariaceae": 3744,  # porzeczki, agrest
    "Vitaceae": 6672,  # winogrona
    "Musaceae": 3733,  # banany
    "Bromeliaceae": 5225,  # ananasy
    "Lauraceae": 3686,  # awokado
    "Anacardiaceae": 3920,  # mango, pistacje
    "Moraceae": 4690,  # figi
    "Arecaceae": 3764,  # palmy kokosowe, daktyle
    "Actinidiaceae": 6680,  # kiwi
    "Passifloraceae": 6676,  # marakuja
    "Myrtaceae": 3762,  # gujawa
    "Ebenaceae": 4374,  # persimmon (hurma)
    "Caricaceae": 4302,  # papaja
    "Punicaceae": 6702,  # granat
}
# nubKey dla Rosaceae 5015


def _pl_names_from_nub(nub_key: int, seen_nubs: set[int]) -> set[str]:
    """Zwraca polskie nazwy zwyczajowe dla nubKey, albo pusty set."""
    if nub_key in seen_nubs:
        return set()
    seen_nubs.add(nub_key)
    time.sleep(0.15)
    try:
        vn_data = species.name_usage(key=nub_key, data="vernacularNames")
    except Exception:
        return set()
    vn_list = vn_data.get("results", []) if isinstance(vn_data, dict) else vn_data
    out: set[str] = set()
    for rec in vn_list:
        lang = (rec.get("language") or "").lower()
        name = str(rec.get("vernacularName") or "").strip()
        if lang in ("pl", "pol") or not lang and any(c in POLISH_CHARS for c in name):
            out.add(name)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--csv", type=Path, default=REPO_ROOT / "data" / "gbif_pl_fruits.csv")
    ap.add_argument("--max-per-family", type=int, default=60, help="Max species per family")
    args = ap.parse_args()

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    existing = set(load_plant_norms_from_seed_file())
    new_norms: set[str] = set()
    csv_rows: list[dict] = []
    seen_nubs: set[int] = set()
    total_pl = 0

    for fam_name, nub_key in sorted(FAMILY_NUBKEYS.items()):
        print(f"\n{fam_name} (nubKey={nub_key})...", flush=True)
        try:
            res = species.name_lookup(
                higherTaxonKey=nub_key,
                rank="SPECIES",
                limit=args.max_per_family,
                offset=0,
            )
        except Exception as e:
            print(f"  ❌ błąd: {e}")
            continue
        results = res.get("results", [])
        if not results:
            print("  — brak wyników")
            continue
        print(f"  {len(results)} gatunków")

        for row in results:
            sci = row.get("scientificName", "?")
            nub = row.get("nubKey")
            if not nub or nub in seen_nubs:
                continue
            pl_names = _pl_names_from_nub(nub, seen_nubs)
            if not pl_names:
                continue

            total_pl += 1
            print(f"  ✓ {list(pl_names)[0]:20} ({sci[:40]})")
            if total_pl <= 3 or total_pl % 25 == 0:
                print(f"     → {sorted(pl_names)}")

            # Pobierz też EN nazwy
            time.sleep(0.1)
            try:
                en_vn = species.name_usage(key=nub, data="vernacularNames")
                en_vn_list = en_vn.get("results", []) if isinstance(en_vn, dict) else en_vn
            except Exception:
                en_vn_list = []
            en_names = [
                str(rec.get("vernacularName", ""))
                for rec in en_vn_list
                if rec.get("language") == "en"
            ]

            for pn in pl_names:
                n = norm_game(pn)
                if keep_fauna_flora_name(pn) and len(n) >= 2 and n not in existing:
                    new_norms.add(n)

            csv_rows.append(
                {
                    "family": fam_name,
                    "scientific": sci,
                    "nubKey": nub,
                    "pl_names": "; ".join(sorted(pl_names)),
                    "en_names": "; ".join(sorted(set(en_names))),
                }
            )

    actually_new = new_norms - existing
    print(f"\n{'=' * 60}")
    print(f"Rodzin: {len(FAMILY_NUBKEYS)}")
    print(f"Z PL nazwami: {total_pl}")
    print(f"Nowe normy: {len(actually_new)} → {sorted(actually_new)[:30]}...")

    with args.csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "family",
                "scientific",
                "nubKey",
                "pl_names",
                "en_names",
            ],
        )
        w.writeheader()
        w.writerows(csv_rows)
    print(f"CSV: {args.csv} ({len(csv_rows)} wierszy)")

    if args.apply and actually_new:
        merged = existing | actually_new
        write_plant_norms_jsonl_gz(merged)
        print(f"plant_norms: {len(existing)} → {len(merged)}")
    elif not args.apply and actually_new:
        print("Użyj --apply, żeby zapisać")


if __name__ == "__main__":
    main()
