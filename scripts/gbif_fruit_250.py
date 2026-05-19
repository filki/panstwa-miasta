#!/usr/bin/env python3
"""Szuka ~250 owoców z polskimi nazwami w GBIF.

Dla listy angielskich nazw owoców/warzyw/grzybów/orzechów:
1. Szuka w GBIF species/search (bez status=ACCEPTED, bo ogranicza wyniki)
2. Bierze pierwszy wynik z Plantae
3. Pobiera vernacular names → wyciąga polskie i angielskie
4. Zapisuje CSV z mapowaniem + dopisuje polskie normy do plant_norms

    uv run python scripts/gbif_fruit_250.py --dry-run
    uv run python scripts/gbif_fruit_250.py --apply
"""

from __future__ import annotations

import argparse
import csv
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
UA = "PanstwaMiasta/1.0 (+https://github.com/filki/panstwa-miasta; fruit250)"

POLISH_CHARS = frozenset("ąćęłńóśźż")

FRUIT_QUERIES: list[str] = [
    # === Temperate fruits ===
    "apple",
    "pear",
    "plum",
    "cherry",
    "sweet cherry",
    "sour cherry",
    "peach",
    "nectarine",
    "apricot",
    "grape",
    "strawberry",
    "raspberry",
    "blackberry",
    "blueberry",
    "cranberry",
    "red currant",
    "black currant",
    "gooseberry",
    "elderberry",
    "fig",
    "mulberry",
    "persimmon",
    "quince",
    "medlar",
    "loquat",
    "rhubarb",
    "lingonberry",
    "cloudberry",
    "bilberry",
    "huckleberry",
    "boysenberry",
    "loganberry",
    "goji berry",
    "sea buckthorn",
    "rose hip",
    "rowan berry",
    "chokeberry",
    "serviceberry",
    "barberry",
    # === Citrus ===
    "orange",
    "lemon",
    "lime",
    "tangerine",
    "mandarin",
    "kumquat",
    "citron",
    "pomelo",
    "grapefruit",
    # === Tropical fruits ===
    "banana",
    "pineapple",
    "mango",
    "papaya",
    "avocado",
    "kiwi",
    "passion fruit",
    "guava",
    "lychee",
    "dragon fruit",
    "durian",
    "jackfruit",
    "breadfruit",
    "star fruit",
    "rambutan",
    "mangosteen",
    "tamarind",
    "date fruit",
    "coconut",
    "pomegranate",
    "olive",
    "sugar apple",
    "custard apple",
    "cherimoya",
    "soursop",
    "longan",
    "jujube",
    "tamarillo",
    "feijoa",
    "prickly pear",
    "acai berry",
    # === Melons ===
    "watermelon",
    "cantaloupe",
    "honeydew",
    "bitter melon",
    # === Nuts ===
    "almond",
    "walnut",
    "pecan",
    "cashew",
    "pistachio",
    "hazelnut",
    "macadamia",
    "brazil nut",
    "chestnut",
    "pine nut",
    "peanut",
    # === Vegetables ===
    "tomato",
    "cucumber",
    "pumpkin",
    "zucchini",
    "eggplant",
    "bell pepper",
    "chili pepper",
    "carrot",
    "potato",
    "sweet potato",
    "yam",
    "cassava",
    "broccoli",
    "cauliflower",
    "cabbage",
    "kale",
    "spinach",
    "lettuce",
    "onion",
    "garlic",
    "leek",
    "shallot",
    "chive",
    "celery",
    "asparagus",
    "artichoke",
    "beetroot",
    "radish",
    "turnip",
    "parsnip",
    "pea",
    "green bean",
    "fava bean",
    "soybean",
    "lentil",
    "chickpea",
    "corn",
    "okra",
    "kohlrabi",
    # === Herbs ===
    "basil",
    "parsley",
    "dill",
    "coriander",
    "mint",
    "oregano",
    "thyme",
    "rosemary",
    "sage",
    "tarragon",
    "fennel",
    "anise",
    "caraway",
    "cumin",
    "turmeric",
    "ginger",
    "lemongrass",
    # === Mushrooms ===
    "mushroom",
    "porcini",
    "chanterelle",
    "truffle",
    "shiitake",
    "morel",
    "oyster mushroom",
    # === Grains ===
    "wheat",
    "barley",
    "oats",
    "rye",
    "rice",
    "quinoa",
    "buckwheat",
    "millet",
]


def search_gbif(client: httpx.Client, query: str) -> list[dict]:
    r = client.get(
        f"{GBIF_API}/species/search",
        params={"q": query, "limit": 5},
    )
    r.raise_for_status()
    return list(r.json().get("results") or [])


def get_vernacular(client: httpx.Client, usage_key: int) -> list[dict]:
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
    ap.add_argument("--csv", type=Path, default=REPO_ROOT / "data" / "gbif_fruit_250.csv")
    args = ap.parse_args()

    args.csv.parent.mkdir(parents=True, exist_ok=True)

    existing = set(load_plant_norms_from_seed_file())
    new_norms: set[str] = set()
    found_count = 0
    csv_rows: list[dict] = []

    headers = {"User-Agent": UA}
    with httpx.Client(timeout=30.0, headers=headers) as client:
        for idx, en_query in enumerate(FRUIT_QUERIES, 1):
            print(f"[{idx}/{len(FRUIT_QUERIES)}] {en_query}...", end=" ", flush=True)

            try:
                results = search_gbif(client, en_query)
            except httpx.HTTPError:
                print("ERR")
                time.sleep(1.0)
                continue

            best = None
            for row in results:
                k = row.get("kingdom")
                if k in ("Plantae", "Fungi"):
                    best = row
                    break

            if best is None:
                print("—")
                time.sleep(0.4)
                continue

            key = best.get("key") or best.get("acceptedKey")
            scientific = best.get("scientificName", "?")
            kingdom = best.get("kingdom", "?")

            time.sleep(0.3)
            try:
                vn_records = get_vernacular(client, int(key))
            except httpx.HTTPError:
                print("—")
                time.sleep(0.4)
                continue

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
                elif not lang and any(c in POLISH_CHARS for c in name):
                    pl_names.append(name)

            if not pl_names:
                print("—")
                time.sleep(0.4)
                continue

            found_count += 1
            print(f"{pl_names[0]}")

            for pn in pl_names:
                n = norm_game(pn)
                if keep_fauna_flora_name(pn) and len(n) >= 2:
                    if n not in existing:
                        new_norms.add(n)

            csv_rows.append(
                {
                    "english_query": en_query,
                    "scientific_name": scientific,
                    "species_key": key,
                    "kingdom": kingdom,
                    "en_names": "; ".join(sorted(set(en_names))),
                    "pl_names": "; ".join(sorted(set(pl_names))),
                }
            )
            time.sleep(0.4)

    actually_new = new_norms - existing
    print(f"\n{'=' * 60}")
    print(f"Zapytań: {len(FRUIT_QUERIES)}, z PL: {found_count}")
    print(f"Nowe normy: {len(actually_new)}")

    with args.csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "english_query",
                "scientific_name",
                "species_key",
                "kingdom",
                "en_names",
                "pl_names",
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
        print(f"Użyj --apply, żeby zapisać ({len(actually_new)} nowych)")


if __name__ == "__main__":
    main()
