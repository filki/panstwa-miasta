#!/usr/bin/env python3
"""Skrapuje polską Wikipedię (BS4) — kategorie ze stronami gatunków → ``animals_norms.jsonl.gz``.

Wymaga sieci. Szanuj serwer: opóźnienia między stronami.

    uv run python scripts/build_animals_wikipedia_bs4.py

Domyślne kategorie + **Wikiprojekt Zoologia / Zwierzęta świata** (wikitable z
polskimi nazwami) dają zwykle **>5000** unikalnych tytułów (po normalizacji).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from seed_scrape_common import norm_game, polite_sleep

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "scripts" / "seed_data" / "animals_norms.jsonl.gz"

UA = {
    "User-Agent": "PanstwaMiasta/1.0 (+https://github.com/filki/panstwa-miasta; animals seed BS4)"
}

# Lista przekierowań polskich nazw zwierząt (kolumna „Strona” w wikitable).
ZOOLOGY_WIKIPROJECT_URL = (
    "https://pl.wikipedia.org/wiki/Wikiprojekt:Zoologia/przekierowania/Zwierz%C4%99ta_%C5%9Bwiata"
)

# Kategorie z sekcją „Strony w kategorii” (#mw-pages) i paginacją pagefrom= (skórka Vector).
DEFAULT_CATEGORIES = [
    "https://pl.wikipedia.org/wiki/Kategoria:Gatunki_i_podgatunki_zwierz%C4%85t_nazwane_w_1758_roku",
    "https://pl.wikipedia.org/wiki/Kategoria:Motyle_Europy",
    "https://pl.wikipedia.org/wiki/Kategoria:Motyle_Azji",
    "https://pl.wikipedia.org/wiki/Kategoria:Chrz%C4%85szcze_Europy",
    "https://pl.wikipedia.org/wiki/Kategoria:Motyle_Afryki",
    "https://pl.wikipedia.org/wiki/Kategoria:Zwierz%C4%99ta",
    "https://pl.wikipedia.org/wiki/Kategoria:Ptaki",
    "https://pl.wikipedia.org/wiki/Kategoria:Owady",
    "https://pl.wikipedia.org/wiki/Kategoria:Ryby",
    "https://pl.wikipedia.org/wiki/Kategoria:Gady",
    "https://pl.wikipedia.org/wiki/Kategoria:P%C5%82azy",
]


def titles_from_category_html(html: str) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: set[str] = set()
    for a in soup.select("#mw-pages .mw-category-group li a"):
        href = (a.get("href") or "").strip()
        if not href or "Kategoria:" in href:
            continue
        title = (a.get("title") or a.get_text(strip=True) or "").strip()
        if not title or title.startswith("Kategoria:"):
            continue
        n = norm_game(title)
        if len(n) >= 2 and not re.fullmatch(r"[\d\s.\-]+", n):
            out.add(n)
    return out


def titles_from_zoology_redirects_table(html: str) -> set[str]:
    """Tytuły z pierwszej kolumny „Strona” w wikitable Wikiprojektu Zoologia."""
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.wikitable")
    if not table:
        return set()
    out: set[str] = set()
    for tr in table.select("tr")[1:]:
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 2:
            continue
        strona = tds[1]
        for a in strona.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href or "Kategoria:" in href or "Specjalna:" in href:
                continue
            title = (a.get("title") or a.get_text(strip=True) or "").strip()
            if not title or title.startswith("Kategoria:"):
                continue
            n = norm_game(title)
            if len(n) >= 2 and not re.fullmatch(r"[\d\s.\-]+", n):
                out.add(n)
    return out


def next_category_url(html: str, current_url: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    nxt = soup.select_one("a.mw-nextlink")
    if nxt and nxt.get("href"):
        return urljoin(current_url, nxt["href"])
    # Skórka Vector: „następna strona” → index.php?...&pagefrom=...
    pages = soup.select_one("#mw-pages")
    if pages:
        for a in pages.select("a[href]"):
            href = a.get("href") or ""
            if "pagefrom=" not in href and "pageuntil=" not in href:
                continue
            label = (a.get_text(strip=True) or "").lower()
            if "następn" in label or "next page" in label:
                return urljoin(current_url, href)
        for a in pages.select('a[href*="pagefrom="]'):
            return urljoin(current_url, a["href"])
    return None


def crawl_category(client: httpx.Client, start_url: str, cap: int) -> set[str]:
    collected: set[str] = set()
    url: str | None = start_url
    seen_urls: set[str] = set()
    while url and len(collected) < cap:
        if url in seen_urls:
            break
        seen_urls.add(url)
        r = client.get(url)
        r.raise_for_status()
        batch = titles_from_category_html(r.text)
        collected |= batch
        if len(collected) >= cap:
            break
        nxt = next_category_url(r.text, url)
        if not nxt or nxt == url:
            break
        url = nxt
        polite_sleep(0.45)
    return collected


def main() -> None:
    cap = 8000
    all_titles: set[str] = set()
    with httpx.Client(headers=UA, timeout=120.0, follow_redirects=True) as client:
        for cat_url in DEFAULT_CATEGORIES:
            if len(all_titles) >= cap:
                break
            chunk = crawl_category(client, cat_url, cap - len(all_titles))
            all_titles |= chunk
            polite_sleep(0.6)

        r = client.get(ZOOLOGY_WIKIPROJECT_URL)
        r.raise_for_status()
        extra = titles_from_zoology_redirects_table(r.text)
        all_titles |= extra
        polite_sleep(1.0)

    if len(all_titles) < 2000:
        print(f"UWAGA: tylko {len(all_titles)} nazw — sprawdź sieć lub źródła.", file=sys.stderr)

    from panstwa_miasta.seed_data_loader import write_animal_norms_jsonl_gz

    n = write_animal_norms_jsonl_gz(all_titles)
    print(f"Zapisano {n} norm → {OUT}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        print(f"Błąd HTTP: {e}", file=sys.stderr)
        sys.exit(1)
