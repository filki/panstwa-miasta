#!/usr/bin/env python3
"""Uzupełnij tabelę `animals` o brakujące zwierzęta z `animal_norms`.

1. Pobiera wszystkie `animal_norms` z Turso.
2. Sprawdza które już są w `animals` (po nazwa_norm).
3. Dla brakujących: SPARQL batch (500) → Wikidata → nazwa_lacinska, rodzina, rodzaj.
4. INSERT OR IGNORE do `animals`.

Usage:
    uv run python scripts/seed_animals_sparql.py

Output:
    Zwierzęta w tabeli `animals` w Turso.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

_SPARQL_URL = "https://query.wikidata.org/sparql"
_USER_AGENT = "PanstwaMiasta/1.0"
_BATCH_SIZE = 500
_SLEEP = 1  # seconds between batches (rate limit)

QUERY_TPL = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?item ?plLabel ?scientific ?familyLabel ?genusLabel WHERE {
  VALUES ?plLabel { $VALS }
  {
    ?item wdt:P1843 ?plLabel . FILTER(LANG(?plLabel)="pl")
  } UNION {
    ?item rdfs:label ?plLabel . FILTER(LANG(?plLabel)="pl")
  }
  ?item wdt:P31 wd:Q729 .
  ?item wdt:P225 ?scientific .
  OPTIONAL {
    ?item wdt:P171 ?familyItem .
    ?familyItem wdt:P105 wd:Q35409 .
  }
  OPTIONAL {
    ?item wdt:P171 ?genusItem .
    ?genusItem wdt:P105 wd:Q34740 .
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pl,en". }
}
"""


def _sqlesc(s: str) -> str:
    return "'" + s.replace("'", "\\'").replace("\\", "\\\\") + "'@pl"


def _normalize(text: str) -> str:
    m = str.maketrans(
        {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
    )
    return text.lower().strip().translate(m)


def _run_sparql(query: str) -> list[dict]:
    data = urllib.parse.urlencode({"format": "json", "query": query}).encode()
    req = urllib.request.Request(_SPARQL_URL, data=data)
    req.add_header("User-Agent", _USER_AGENT)
    req.add_header("Accept", "application/sparql-results+json")

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
                return body.get("results", {}).get("bindings", [])
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            print(f"  SPARQL error (attempt {attempt + 1}): {e}", file=sys.stderr)
            if attempt < 2:
                time.sleep(5)
    return []


def _turso(sql: str) -> str:
    r = os.popen(f'turso db shell panstwa-miasta "{" ".join(sql.split())}"')
    out = r.read()
    r.close()
    return out.strip()


def main() -> None:
    print("=== Seed Animals from Wikidata SPARQL ===\n")

    # 1. Load all norms
    print("Pobieram animal_norms z Turso...")
    rows = _turso("SELECT norm FROM animal_norms ORDER BY norm;")
    all_norms = [line.strip() for line in rows.split("\n") if line.strip() and line.strip() != "NORM"]
    print(f"  animal_norms: {len(all_norms)}")

    # 2. Load existing nazwa_norm z animals
    existing = _turso("SELECT nazwa_norm FROM animals;")
    existing_set = set(
        line.strip() for line in existing.split("\n") if line.strip() and line.strip() != "NAZWA_NORM"
    )
    print(f"  already in animals: {len(existing_set)}")

    # 3. Brakujące
    missing = [n for n in all_norms if _normalize(n) not in existing_set]
    print(f"  brakuje w animals: {len(missing)}")

    if not missing:
        print("Wszystkie już załadowane.")
        return

    # 4. SPARQL batch
    print(f"\nSzukam w Wikidata ({len(missing)} nazw, batch {_BATCH_SIZE})...")
    results: list[dict] = []
    seen_items: set[str] = set()
    batch_num = 0

    for start in range(0, len(missing), _BATCH_SIZE):
        batch = missing[start : start + _BATCH_SIZE]
        batch_num += 1
        vals = " ".join(_sqlesc(n) for n in batch)
        query = QUERY_TPL.replace("$VALS", vals)

        print(f"  Batch {batch_num}: {len(batch)} nazw...", end=" ", flush=True)
        bindings = _run_sparql(query)
        print(f"{len(bindings)} matchy", flush=True)

        for b in bindings:
            item = b["item"]["value"]
            if item in seen_items:
                continue
            seen_items.add(item)

            pl_label = b.get("plLabel", {}).get("value", "")
            scientific = b.get("scientific", {}).get("value", "")
            family = b.get("familyLabel", {}).get("value", "")
            genus = b.get("genusLabel", {}).get("value", "")

            if not pl_label:
                continue

            results.append(
                {
                    "nazwa": pl_label,
                    "nazwa_norm": _normalize(pl_label),
                    "nazwa_lacinska": scientific,
                    "rodzina": family,
                    "rodzaj": genus,
                    "kategoria_zagrozenia": "",
                }
            )

        time.sleep(_SLEEP)

    print(f"\nZnaleziono {len(results)} nowych zwierząt.")

    # 5. INSERT do Turso
    if results:
        print("Wstawiam do Turso...")
        inserted = 0
        for row in results:
            sql = (
                "INSERT OR IGNORE INTO animals (nazwa, nazwa_norm, nazwa_lacinska, rodzina, rodzaj, kategoria_zagrozenia) "
                f"VALUES ({json.dumps(row['nazwa'])}, {json.dumps(row['nazwa_norm'])}, "
                f"{json.dumps(row['nazwa_lacinska'])}, {json.dumps(row['rodzina'])}, "
                f"{json.dumps(row['rodzaj'])}, '')"
            )
            _turso(sql)
            inserted += 1

        # podsumowanie
        total = _turso("SELECT COUNT(*) FROM animals;")
        print(f"  Wstawiono: {inserted}")
        print(f"  Razem w animals: {total}")

    print("\n=== Gotowe ===")


if __name__ == "__main__":
    main()
