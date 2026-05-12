#!/usr/bin/env python3
"""Buduje ``cities_seed_pl_generated.py`` z Wikidata (SPARQL): miasta w Polsce, etykieta PL.

Wymaga sieci. Używa ``httpx`` (już w zależnościach projektu), nie ``requests``.

    uv run python scripts/build_polish_cities_wikidata.py

Nazwy przechodzą przez ``panstwa_miasta.city_name_rules.keep_city_name_for_pl_game``.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

from panstwa_miasta.city_name_rules import keep_city_name_for_pl_game

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "src" / "panstwa_miasta" / "cities_seed_pl_generated.py"
WD_URL = "https://query.wikidata.org/sparql"
UA = "PanstwaMiasta/1.0 (+https://github.com; Wikidata SPARQL; polish cities seed)"

PAGE = 5000

QUERY_TEMPLATE = """
SELECT DISTINCT ?cityLabel WHERE {{
  ?city wdt:P31/wdt:P279* wd:Q515 ;
        wdt:P17 wd:Q36 .
  ?city rdfs:label ?cityLabel .
  FILTER(LANG(?cityLabel) = "pl")
}}
ORDER BY ?cityLabel
LIMIT {limit}
OFFSET {offset}
"""


def fetch_all_labels() -> list[str]:
    labels: list[str] = []
    offset = 0
    headers = {"User-Agent": UA, "Accept": "application/sparql-results+json"}
    with httpx.Client(timeout=120.0, headers=headers) as client:
        while True:
            query = QUERY_TEMPLATE.format(limit=PAGE, offset=offset)
            for attempt in range(5):
                r = client.get(WD_URL, params={"query": query, "format": "json"})
                if r.status_code in (429, 503):
                    time.sleep(15 * (attempt + 1))
                    continue
                r.raise_for_status()
                break
            else:
                raise RuntimeError("Wikidata SPARQL: zbyt wiele prób po 429/503")

            data = r.json()
            bindings = data.get("results", {}).get("bindings", [])
            if not bindings:
                return labels
            for b in bindings:
                labels.append(str(b["cityLabel"]["value"]))
            if len(bindings) < PAGE:
                return labels
            offset += PAGE
            time.sleep(0.35)


def main() -> None:
    print("Pobieranie z Wikidata…")
    raw = fetch_all_labels()
    print(f"  surowo: {len(raw)} etykiet")

    seen: dict[str, None] = {}
    for name in raw:
        if not keep_city_name_for_pl_game(name):
            continue
        seen.setdefault(name, None)

    rows = sorted(seen.keys(), key=lambda s: (s.casefold(), s))
    kraj = "Polska"

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    body = "\n".join(f'    ("{esc(n)}", "{esc(kraj)}"),' for n in rows)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    content = f'''"""Miasta w Polsce z Wikidata (SPARQL), etykiety języka ``pl``.

Wygenerowano: {stamp}
Skrypt: ``scripts/build_polish_cities_wikidata.py``.
Filtr nazw: ``panstwa_miasta.city_name_rules``.

Nie edytuj ręcznie — odtwórz skryptem.
"""

from __future__ import annotations

from typing import Final

CITIES_SEED_PL_WIKI: Final[list[tuple[str, str]]] = [
{body}
]
'''
    OUT_PATH.write_text(content, encoding="utf-8")
    print(f"Zapisano {len(rows)} wpisów → {OUT_PATH}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        print(f"Błąd HTTP: {e}", file=sys.stderr)
        sys.exit(1)
