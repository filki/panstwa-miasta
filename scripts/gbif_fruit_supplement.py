#!/usr/bin/env python3
"""Pobiera z GBIF angielskie i polskie nazwy owoców + dane taksonomiczne.

Dla listy potocznych polskich nazw owoców/warzyw szuka w GBIF:
- species key, scientific name, kingdom, rank
- angielskie nazwy zwyczajowe (language=en)
- polskie nazwy zwyczajowe (language=pl/pol)

Wynik: CSV z mapowaniem + opcjonalnie dopisanie polskich nazw do plant_norms.

    uv run python scripts/gbif_fruit_supplement.py --dry-run
    uv run python scripts/gbif_fruit_supplement.py --apply
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from panstwa_miasta.gbif_seed import keep_fauna_flora_name, norm_game
from panstwa_miasta.seed_data_loader import (
    load_plant_norms_from_seed_file,
    write_plant_norms_jsonl_gz,
)

GBIF_API = "https://api.gbif.org/v1"
UA = "PanstwaMiasta/1.0 (+https://github.com/filki/panstwa-miasta; fruit supplement)"

# Polskie potoczne nazwy owoców/warzyw — gracze oczekują że przejdą jako "Roślina".
# Każda ma przypisaną angielską kwerendę do GBIF (nazwa gatunku po angielsku).
FRUIT_QUERIES: dict[str, str] = {
    # Owoce
    "jabłko": "apple",
    "gruszka": "pear",
    "śliwka": "plum",
    "brzoskwinia": "peach",
    "morela": "apricot",
    "nektarynka": "nectarine",
    "wiśnia": "cherry",
    "czereśnia": "sweet cherry",
    "winogrono": "grape",
    "truskawka": "strawberry",
    "malina": "raspberry",
    "jeżyna": "blackberry",
    "borówka": "blueberry",
    "porzeczka": "currant",
    "agrest": "gooseberry",
    "poziomka": "wild strawberry",
    "jagoda": "berry",
    "banan": "banana",
    "pomarańcza": "orange",
    "cytryna": "lemon",
    "mandarynka": "mandarin",
    "grejpfrut": "grapefruit",
    "limonka": "lime",
    "ananas": "pineapple",
    "arbuz": "watermelon",
    "melon": "melon",
    "mango": "mango",
    "awokado": "avocado",
    "kiwi": "kiwi",
    "granat": "pomegranate",
    "figa": "fig",
    "daktyle": "date",
    "kokos": "coconut",
    # Warzywa (często wpisywane jako rośliny)
    "pomidor": "tomato",
    "ogórek": "cucumber",
    "dynia": "pumpkin",
    "cukinia": "zucchini",
    "bakłażan": "eggplant",
    "papryka": "pepper",
    "marchew": "carrot",
    "ziemniak": "potato",
    "brokuł": "broccoli",
    "kalafior": "cauliflower",
    "kapusta": "cabbage",
    "sałata": "lettuce",
    "cebula": "onion",
    "czosnek": "garlic",
    "pietruszka": "parsley",
}


def search_gbif(client: httpx.Client, query: str) -> list[dict]:
    """Szuka w GBIF species/search, zwraca wyniki ACCEPTED."""
    r = client.get(
        f"{GBIF_API}/species/search",
        params={"q": query, "limit": 5, "status": "ACCEPTED"},
    )
    r.raise_for_status()
    return list(r.json().get("results") or [])


def get_vernacular(client: httpx.Client, usage_key: int) -> list[dict]:
    """Pobiera vernacularNames dla gatunku."""
    r = client.get(
        f"{GBIF_API}/species/{usage_key}/vernacularNames",
        params={"limit": 500},
    )
    r.raise_for_status()
    return list(r.json().get("results") or [])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--csv", type=Path, default=REPO_ROOT / "data" / "gbif_fruit_map.csv")
    args = ap.parse_args()

    # Przygotuj output CSV
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    csv_rows: list[dict] = []

    existing = set(load_plant_norms_from_seed_file())
    new_norms: set[str] = set()
    already_there: set[str] = set()

    headers = {"User-Agent": UA}
    with httpx.Client(timeout=30.0, headers=headers) as client:
        for pl_name, en_query in sorted(FRUIT_QUERIES.items()):
            print(f"\n{pl_name} (query: {en_query!r})", flush=True)

            try:
                results = search_gbif(client, en_query)
            except httpx.HTTPError as e:
                print(f"  ❌ błąd HTTP: {e}")
                time.sleep(1.0)
                continue

            if not results:
                print(f"  ⚠️  brak wyników")
                # Dodajemy samą nazwę jako fallback jeśli nie ma w seedzie
                n = norm_game(pl_name)
                if n not in existing:
                    new_norms.add(n)
                    print(f"  → fallback: dodaję '{n}'")
                continue

            best = results[0]
            key = best.get("key") or best.get("acceptedKey")
            scientific = best.get("scientificName", "")
            kingdom = best.get("kingdom", "")
            rank = best.get("rank", "")

            # Pobierz nazwy zwyczajowe
            time.sleep(0.3)
            try:
                vn_records = get_vernacular(client, int(key))
            except httpx.HTTPError:
                vn_records = []
                print(f"  ⚠️  brak vernacularNames")

            en_names: list[str] = []
            pl_names: list[str] = []
            for rec in vn_records:
                lang = (rec.get("language") or "").lower()
                name = str(rec.get("vernacularName") or "").strip()
                if not name:
                    continue
                if lang == "en":
                    en_names.append(name)
                elif lang in ("pl", "pol"):
                    pl_names.append(name)
                elif not lang and any(c in "ąćęłńóśźż" for c in name):
                    pl_names.append(name)

            print(f"  🔬 {scientific} ({kingdom}, {rank})")
            print(f"  🇬🇧 en: {en_names}")
            print(f"  🇵🇱 pl: {pl_names}")

            # Dodaj polskie nazwy do zbioru
            for pn in pl_names:
                n = norm_game(pn)
                if keep_fauna_flora_name(pn) and len(n) >= 2:
                    if n in existing:
                        already_there.add(n)
                    else:
                        new_norms.add(n)
                        print(f"  → +{n}")

            # Dodaj też samą kwerendę (polską nazwę potoczną) jeśli nie ma
            n_pl = norm_game(pl_name)
            if n_pl not in existing and n_pl not in {norm_game(x) for x in pl_names}:
                new_norms.add(n_pl)
                print(f"  → +{n_pl} (nazwa potoczna)")

            csv_rows.append(
                {
                    "polish_name": pl_name,
                    "english_query": en_query,
                    "species_key": key,
                    "scientific_name": scientific,
                    "kingdom": kingdom,
                    "rank": rank,
                    "en_vernacular": "; ".join(sorted(set(en_names))),
                    "pl_vernacular": "; ".join(sorted(set(pl_names))),
                }
            )
            time.sleep(0.5)

    # Podsumowanie
    print(f"\n{'=' * 60}")
    print(f"Już w seedzie: {len(already_there)}")
    print(f"Nowe normy: {len(new_norms)} → {sorted(new_norms)}")

    # Zapisz CSV z mapowaniem
    with args.csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "polish_name",
                "english_query",
                "species_key",
                "scientific_name",
                "kingdom",
                "rank",
                "en_vernacular",
                "pl_vernacular",
            ],
        )
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"CSV zapisano: {args.csv} ({len(csv_rows)} wierszy)")

    # Aplikuj do seeda
    if args.apply and new_norms:
        merged = existing | new_norms
        write_plant_norms_jsonl_gz(merged)
        print(f"Zaktualizowano plants_norms.jsonl.gz: {len(existing)} → {len(merged)}")
    elif not args.apply:
        print(f"Użyj --apply, żeby zapisać nowe normy do seeda.")


if __name__ == "__main__":
    main()
