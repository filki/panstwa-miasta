#!/usr/bin/env python3
"""Flora (kategoria gry „Roślina”): BS4 z zielonyogrodek.pl + uzupełnienie z en.wikipedia.

Zakres: rośliny ozdobne, **krzewy i drzewa**, **owoce / warzywa** (katalog
``owocowe-warzywne``), **zioła**, byliny, cebulowe, pnącza, rośliny doniczkowe,
jednoroczne, balkon/taras, wodne itd. — jedna lista ``PLANTS_NORMS`` pod pole
``Roślina`` w grze.

Wymaga sieci.

    uv run python scripts/build_plants_bs4.py

Cel: **≥2000** unikalnych nazw po ``norm_game`` (PL z katalogu + EN z listy).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from seed_scrape_common import norm_game, polite_sleep, write_frozenset_module

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "src" / "panstwa_miasta" / "plants_seed_generated.py"

UA = {"User-Agent": "PanstwaMiasta/1.0 (+https://github.com/filki/panstwa-miasta; plants seed BS4)"}

# Wszystkie główne gałęzie katalogu /katalog-roslin/ (flora szeroko rozumiana).
ZIELONY_CATALOG_BASES = [
    "https://zielonyogrodek.pl/katalog-roslin/byliny",
    "https://zielonyogrodek.pl/katalog-roslin/cebulowe",
    "https://zielonyogrodek.pl/katalog-roslin/do-wnetrz",
    "https://zielonyogrodek.pl/katalog-roslin/drzewa",
    "https://zielonyogrodek.pl/katalog-roslin/jednoroczne-dwuletnie",
    "https://zielonyogrodek.pl/katalog-roslin/krzewy",
    "https://zielonyogrodek.pl/katalog-roslin/na-balkon-i-taras",
    "https://zielonyogrodek.pl/katalog-roslin/owocowe-warzywne",
    "https://zielonyogrodek.pl/katalog-roslin/pnacza",
    "https://zielonyogrodek.pl/katalog-roslin/wodne",
    "https://zielonyogrodek.pl/katalog-roslin/ziola",
    "https://zielonyogrodek.pl/katalog-roslin/inne",
]

# Alfabet „na literę”: a–z + dodatkowe segmenty URL z diakrytyką (jak w menu serwisu).
LETTER_PATH_SEGMENTS: tuple[str, ...] = tuple("abcdefghijklmnopqrstuvwxyz") + (
    "%C4%85",
    "%C4%99",
    "%C5%82",
    "%C5%84",
    "%C3%B3",
    "%C5%9A",
    "%C5%B9",
    "%C5%BB",
    "%C5%BA",
    "%C5%BC",
)


def polish_from_zielony_link_text(text: str) -> str | None:
    text = text.strip()
    if len(text) < 2:
        return None
    # „NazwaPolskaNazwaŁacińska” — cięcie przed pierwszą wielką literą po małej polskiej.
    m = re.search(r"([a-ząćęłńóśźż])([A-ZĄĆĘŁŃÓŚŹŻ])", text)
    if m and m.start(2) > 0:
        text = text[: m.start(2)].strip()
    # Po cultivarze „'Sort'Łacina…” bez spacji — odetnij przyklejoną drugą nazwę.
    while True:
        mg = re.search(r"'([^']+)'\s*([A-ZĄĆĘŁŃÓŚŹŻa-ząćęłńóśźż])", text)
        if not mg:
            break
        text = text[: mg.start(2)].strip()
    text = re.sub(r"\s+", " ", text)
    n = norm_game(text)
    if len(n) < 2:
        return None
    if n.startswith("http") or "@" in n:
        return None
    return n


def names_from_zielony_page(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/katalog-roslin/[^/]+/\d+-", href):
            continue
        pn = polish_from_zielony_link_text(a.get_text(strip=True))
        if pn:
            out.add(pn)
    return out


def next_zielony_url(html: str, current: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("link", href=True):
        rel = link.get("rel") or []
        if "next" in rel:
            return urljoin(current, link["href"])
    return None


def crawl_zielony_paginated(client: httpx.Client, start_url: str, cap: int, bag: set[str]) -> None:
    url: str | None = start_url
    stagnant = 0
    seen: set[str] = set()
    while url and len(bag) < cap and stagnant < 4:
        if url in seen:
            break
        seen.add(url)
        r = client.get(url)
        if r.status_code != 200:
            break
        got = names_from_zielony_page(r.text)
        if not got:
            stagnant += 1
        else:
            stagnant = 0
            bag |= got
        nxt = next_zielony_url(r.text, url)
        if not nxt or nxt == url:
            break
        url = nxt
        polite_sleep(0.35)


def crawl_zielony_letters(client: httpx.Client, bag: set[str], cap: int) -> None:
    for seg in LETTER_PATH_SEGMENTS:
        if len(bag) >= cap:
            break
        start = f"https://zielonyogrodek.pl/katalog-roslin/l/{seg}/strona/0"
        crawl_zielony_paginated(client, start, cap, bag)


def crawl_zielony_categories(client: httpx.Client, bag: set[str], cap: int) -> None:
    for base in ZIELONY_CATALOG_BASES:
        if len(bag) >= cap:
            break
        crawl_zielony_paginated(client, base, cap, bag)
        polite_sleep(0.5)


def names_from_en_wikipedia_list(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: set[str] = set()
    for li in soup.select(".mw-parser-output li"):
        t = li.get_text(" ", strip=True)
        if "–" not in t and " - " not in t:
            continue
        if len(t) > 110 or len(t) < 6:
            continue
        tl = t.lower()
        if tl.startswith("^") or "retrieved" in tl or "citation" in tl:
            continue
        if "wikimedia" in tl or "category:" in tl:
            continue
        part = re.split(r"\s+[–-]\s+", t, maxsplit=1)[0].strip()
        part = re.sub(r"^[\d\.\)\s]+", "", part).strip()
        if "," in part:
            continue
        n = norm_game(part)
        if len(n) >= 3 and re.match(r"^[a-ząćęłńóśźż]", n):
            out.add(n)
    return out


def main() -> None:
    cap = 2600
    bag: set[str] = set()
    with httpx.Client(headers=UA, timeout=60.0, follow_redirects=True) as client:
        crawl_zielony_categories(client, bag, cap)
        crawl_zielony_letters(client, bag, cap)
        if len(bag) < cap:
            r = client.get("https://en.wikipedia.org/wiki/List_of_plants_by_common_name")
            r.raise_for_status()
            bag |= names_from_en_wikipedia_list(r.text)
            polite_sleep(0.6)

    if len(bag) < 1800:
        print(f"UWAGA: tylko {len(bag)} nazw roślin — sprawdź sieć.", file=sys.stderr)

    n = write_frozenset_module(
        out_path=OUT,
        const_name="PLANTS_NORMS",
        items=bag,
        doc_first_line="Flora (pole Roślina): zielonyogrodek.pl — byliny, drzewa, krzewy, owoce/warzywa, zioła, … + en.wikipedia.",
        generator_script="scripts/build_plants_bs4.py",
    )
    print(f"Zapisano {n} wpisów → {OUT}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        print(f"Błąd HTTP: {e}", file=sys.stderr)
        sys.exit(1)
