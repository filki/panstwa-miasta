#!/usr/bin/env python3
"""Build structured plants table from Wikidata SPARQL + existing plant_norms.

Strategy:
  1. Fetch all 12k+ plant_norms from Turso.
  2. Filter to "simple" names (no apostrophes, max 3 words, >2 chars).
  3. Batch 300 names at a time via SPARQL VALUES, mapping Polish label → Wikidata item.
  4. For each match: extract scientific name (P225), family (P171 → P105=Q35409).
  5. Save to scripts/seed_data/plants.jsonl.gz (1000 rows for MVP).

Usage:
    uv run python scripts/build_plants_sparql.py

Output:
    scripts/seed_data/plants.jsonl.gz  (1000 rows for Turso / slownik)
"""

from __future__ import annotations

import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_SPARQL_URL = "https://query.wikidata.org/sparql"
_USER_AGENT = "PanstwaMiasta/1.0"
_BATCH_SIZE = 500
_MVP_TARGET = 1000

# SPARQL query template (batch via VALUES)
# Strategy: match by Polish common name (P1843) falling back to rdfs:label.
QUERY_TPL = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?item ?plLabel ?scientific ?familyLabel WHERE {
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
  SERVICE wikibase:label { bd:serviceParam wikibase:language "pl,en". }
}
"""


def _sqlesc(s: str) -> str:
    """Escape a string for SPARQL single-quoted literal."""
    return "'" + s.replace("'", "\\'").replace("\\", "\\\\") + "'@pl"


def _is_simple_name(name: str) -> bool:
    """Filter out names with apostrophes or very long compound names."""
    if "'" in name or '"' in name:
        return False
    if len(name) < 3:
        return False
    word_count = len(name.split())
    if word_count > 4:
        return False
    return True


def _sort_key(name: str) -> tuple:
    """Sort single-word names first (higher hit rate), then 2-word, then 3+."""
    wc = len(name.split())
    return (wc, name)


def _run_sparql(query: str) -> list[dict]:
    """Execute SPARQL query, return results bindings."""
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


def _load_plant_norms_from_turso() -> list[str]:
    """Load plant_norms from Turso CLI."""
    r = os.popen('turso db shell panstwa-miasta "SELECT norm FROM plant_norms ORDER BY norm;"')
    norms = []
    for line in r:
        line = line.strip()
        if not line or line == "NORM":
            continue
        norms.append(line)
    r.close()
    return norms


def _normalize(text: str) -> str:
    """Lowercase + fold Polish diacritics for dedup."""
    m = str.maketrans(
        {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}
    )
    return text.lower().strip().translate(m)


def main() -> None:
    print("Loading plant_norms from Turso...")
    all_norms = _load_plant_norms_from_turso()
    print(f"  {len(all_norms)} norms loaded")

    # Filter simple names
    simple = [n for n in all_norms if _is_simple_name(n)]
    print(f"  {len(simple)} simple names (after filtering long/apostrophe)")

    # Dedup by normalized form
    seen: set[str] = set()
    deduped = []
    for n in simple:
        nf = _normalize(n)
        if nf not in seen:
            seen.add(nf)
            deduped.append(n)
    print(f"  {len(deduped)} after dedup")

    # Sort: single-word first (higher Wikidata hit rate)
    deduped.sort(key=_sort_key)
    print(f"  1-word: {sum(1 for n in deduped if len(n.split()) == 1)}")
    print(f"  2-word: {sum(1 for n in deduped if len(n.split()) == 2)}")

    results: list[dict] = []
    seen_items: set[str] = set()
    batch_num = 0

    for start in range(0, len(deduped), _BATCH_SIZE):
        if len(results) >= _MVP_TARGET:
            break

        batch = deduped[start : start + _BATCH_SIZE]
        batch_num += 1
        vals = " ".join(_sqlesc(n) for n in batch)
        query = QUERY_TPL.replace("$VALS", vals)

        print(f"  Batch {batch_num}: {len(batch)} names...", end=" ", flush=True)

        bindings = _run_sparql(query)
        print(f"{len(bindings)} matches", flush=True)

        for b in bindings:
            item = b["item"]["value"]
            pl_label = b.get("plLabel", {}).get("value", "")
            scientific = b.get("scientific", {}).get("value", "")
            family = b.get("familyLabel", {}).get("value", "")

            if item in seen_items or not pl_label:
                continue
            seen_items.add(item)

            results.append(
                {
                    "nazwa": pl_label,
                    "nazwa_norm": _normalize(pl_label),
                    "nazwa_lacinska": scientific,
                    "rodzina": family,
                    "rodzaj": "",
                }
            )

        time.sleep(1)  # rate limit: ~1 req/s

    # Trim to MVP target
    results = results[:_MVP_TARGET]
    results.sort(key=lambda r: r["nazwa"])

    out_path = REPO_ROOT / "scripts" / "seed_data" / "plants.jsonl.gz"
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        for row in results:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\nDone: {len(results)} plants saved to {out_path}")


if __name__ == "__main__":
    main()
