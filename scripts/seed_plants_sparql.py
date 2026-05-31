#!/usr/bin/env python3
"""Uzupełnij tabelę `plants` o brakujące rośliny z `plant_norms`.

Identyczny pattern co seed_animals_sparql.py, ale:
- Źródło: plant_norms (12782)
- Cel: plants (obecnie 987, < 12782)
- SPARQL: wdt:P31 wd:Q16521 (instance of taxon)

Usage:
    uv run python scripts/seed_plants_sparql.py

Output:
    Rośliny w tabeli `plants` w Turso.
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
_SLEEP = 1

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
  ?item wdt:P31 wd:Q16521 .
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


def _is_simple_name(name: str) -> bool:
    if "'" in name or '"' in name:
        return False
    if len(name) < 3:
        return False
    return True


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
    print("=== Seed Plants from Wikidata SPARQL ===\n")

    # 1. Load all norms
    print("Pobieram plant_norms z Turso...")
    rows = _turso("SELECT norm FROM plant_norms ORDER BY norm;")
    all_norms = [line.strip() for line in rows.split("\n") if line.strip() and line.strip() != "NORM"]
    print(f"  plant_norms: {len(all_norms)}")

    # Filter simple + dedup
    seen: set[str] = set()
    deduped = []
    for n in all_norms:
        if not _is_simple_name(n):
            continue
        nf = _normalize(n)
        if nf not in seen:
            seen.add(nf)
            deduped.append(n)
    deduped.sort(key=lambda n: (len(n.split()), n))  # single-word first
    print(f"  after filter+dedup: {len(deduped)}")

    # 2. Load existing nazwa_norm z plants
    existing = _turso("SELECT nazwa_norm FROM plants;")
    existing_set = set(
        line.strip() for line in existing.split("\n") if line.strip() and line.strip() != "NAZWA_NORM"
    )
    print(f"  already in plants: {len(existing_set)}")

    # 3. Brakujące
    missing = [n for n in deduped if _normalize(n) not in existing_set]
    print(f"  brakuje w plants: {len(missing)}")

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
                }
            )

        time.sleep(_SLEEP)

    print(f"\nZnaleziono {len(results)} nowych roślin.")

    # 5. INSERT do Turso
    if results:
        print("Wstawiam do Turso...")
        inserted = 0
        for row in results:
            sql = (
                "INSERT OR IGNORE INTO plants (nazwa, nazwa_norm, nazwa_lacinska, rodzina, rodzaj) "
                f"VALUES ({json.dumps(row['nazwa'])}, {json.dumps(row['nazwa_norm'])}, "
                f"{json.dumps(row['nazwa_lacinska'])}, {json.dumps(row['rodzina'])}, "
                f"{json.dumps(row['rodzaj'])})"
            )
            _turso(sql)
            inserted += 1

        total = _turso("SELECT COUNT(*) FROM plants;")
        print(f"  Wstawiono: {inserted}")
        print(f"  Razem w plants: {total}")

    print("\n=== Gotowe ===")


if __name__ == "__main__":
    main()
