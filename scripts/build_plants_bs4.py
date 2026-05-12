#!/usr/bin/env python3
"""Flora (kategoria gry „Roślina”): BS4 z zielonyogrodek.pl + atlas-roslin.pl + en.wikipedia.

Zakres: rośliny ozdobne, **krzewy i drzewa**, **owoce / warzywa** (katalog
``owocowe-warzywne``), **zioła**, byliny, cebulowe, pnącza, rośliny doniczkowe,
jednoroczne, balkon/taras, wodne itd. — jedna lista ``PLANTS_NORMS`` pod pole
``Roślina`` w grze.

Wymaga sieci.

    uv run python scripts/build_plants_bs4.py

Cel: duży zbiór unikalnych nazw po ``norm_game`` (PL: Zielony Ogródek + skorowidz
Atlasu roślin Polski + EN z listy Wikipedii).
"""

from __future__ import annotations

import contextlib
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, SoupStrainer
from seed_scrape_common import norm_game, polite_sleep, write_frozenset_module

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "src" / "panstwa_miasta" / "plants_seed_generated.py"

UA = {"User-Agent": "PanstwaMiasta/1.0 (+https://github.com/filki/panstwa-miasta; plants seed BS4)"}

# Skorowidz literowy atlas-roslin.pl (Ł/Ś/Ź/Ż mają nietypowe nazwy plików).
ATLAS_SKOROWIDZ_PAGES: tuple[str, ...] = (
    "A.htm",
    "B.htm",
    "C.htm",
    "D.htm",
    "E.htm",
    "F.htm",
    "G.htm",
    "H.htm",
    "I.htm",
    "J.htm",
    "K.htm",
    "L.htm",
    "LL_.htm",
    "M.htm",
    "N.htm",
    "O.htm",
    "P.htm",
    "Q.htm",
    "R.htm",
    "S.htm",
    "SS_.htm",
    "T.htm",
    "U.htm",
    "V.htm",
    "W.htm",
    "X.htm",
    "XX_.htm",
    "Y.htm",
    "Z.htm",
    "ZZ_.htm",
)

# Rzadkie śmieci z nagłówków / metatekstu skorowidza (nie gatunki).
ATLAS_POLISH_SKIP: frozenset[str] = frozenset(
    {
        "mszaków",
        "efemerofitów",
        "synonimów",
        "chekliście",
        "czekliście",
    }
)

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
    page_i = 0
    while url and len(bag) < cap and stagnant < 4:
        if url in seen:
            break
        seen.add(url)
        page_i += 1
        if page_i == 1 or page_i % 25 == 0:
            print(f"zielony … strona {page_i}, |zbiór|={len(bag)}", flush=True)
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
    print("zielony: indeks A–Z / PL", flush=True)
    for seg in LETTER_PATH_SEGMENTS:
        if len(bag) >= cap:
            break
        start = f"https://zielonyogrodek.pl/katalog-roslin/l/{seg}/strona/0"
        crawl_zielony_paginated(client, start, cap, bag)


def crawl_zielony_categories(client: httpx.Client, bag: set[str], cap: int) -> None:
    for base in ZIELONY_CATALOG_BASES:
        if len(bag) >= cap:
            break
        print(f"zielony kategoria: {base} (|zbiór|={len(bag)})", flush=True)
        crawl_zielony_paginated(client, base, cap, bag)
        polite_sleep(0.5)


def _strip_atlas_leading_markers(text: str) -> str:
    t = text.replace("\xa0", " ").strip()
    return re.sub(r"^[\s\d\.*+—–─!?«»()\[\]✦✧≀]+", "", t).strip()


def _segment_likely_scientific_or_genus_latin(segment: str) -> bool:
    """Odrzuć typowe etykiety łacińskie (Genus, Genus species …) — zostaw polskie części linków."""
    s = _strip_atlas_leading_markers(segment)
    if len(s) < 2:
        return True
    c0 = s[0]
    return bool(c0.isascii() and c0.isupper())


def polish_tokens_from_atlas_anchor_text(text: str) -> set[str]:
    """Wyciąga polskie nazwy z tekstu linku atlas-roslin (np. „… - abelia chińska”)."""
    raw = text.replace("\xa0", " ").strip()
    if not raw or "http" in raw.lower():
        return set()
    if "⟶" in raw or "→" in raw:
        return set()
    out: set[str] = set()
    for part in re.split(r"\s+[-–—]\s+", raw):
        part = _strip_atlas_leading_markers(part)
        if not part or len(part) < 2:
            continue
        if _segment_likely_scientific_or_genus_latin(part):
            continue
        pl = norm_game(part)
        if len(pl) < 2 or len(pl) > 120:
            continue
        if not re.match(r"^[a-ząćęłńóśźż]", pl):
            continue
        if pl in ATLAS_POLISH_SKIP:
            continue
        if " " not in pl and (pl.endswith("aceae") or pl.endswith("owate")):
            continue
        out.add(pl)
    return out


def names_from_atlas_skorowidz_html(html: str) -> set[str]:
    strainer = SoupStrainer("a", href=lambda h: bool(h) and "/gatunki/" in h)
    soup = BeautifulSoup(html, "html.parser", parse_only=strainer)
    out: set[str] = set()
    for a in soup:
        if not hasattr(a, "get"):
            continue
        href = a.get("href") or ""
        if "/gatunki/" not in href:
            continue
        out |= polish_tokens_from_atlas_anchor_text(a.get_text(" ", strip=True))
    return out


def crawl_atlas_skorowidz(client: httpx.Client, bag: set[str], cap: int) -> None:
    base = "https://atlas-roslin.pl/skorowidz/"
    for page in ATLAS_SKOROWIDZ_PAGES:
        if len(bag) >= cap:
            break
        url = urljoin(base, page)
        r = client.get(url)
        if r.status_code != 200:
            print(f"UWAGA: atlas {url} → HTTP {r.status_code}", file=sys.stderr)
            continue
        before = len(bag)
        bag |= names_from_atlas_skorowidz_html(r.text)
        print(f"atlas {page}: +{len(bag) - before} (suma {len(bag)})", flush=True)
        polite_sleep(0.55)


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
    with contextlib.suppress(AttributeError, OSError):
        sys.stdout.reconfigure(line_buffering=True)
    print("build_plants_bs4: start", flush=True)
    # Zielony: ~2.5–3.5k unikalnych norm; dalej rośnie wolno przez paginację — nie trzymaj całego TOTAL_CAP.
    zielony_cap = 2800
    total_cap = 12_000
    bag: set[str] = set()
    with httpx.Client(headers=UA, timeout=120.0, follow_redirects=True) as client:
        crawl_zielony_categories(client, bag, zielony_cap)
        crawl_zielony_letters(client, bag, zielony_cap)
        print(f"zielony: {len(bag)} norm", flush=True)
        crawl_atlas_skorowidz(client, bag, total_cap)
        if len(bag) < total_cap:
            r = client.get("https://en.wikipedia.org/wiki/List_of_plants_by_common_name")
            r.raise_for_status()
            bag |= names_from_en_wikipedia_list(r.text)
            polite_sleep(0.6)

    if len(bag) < 2500:
        print(f"UWAGA: tylko {len(bag)} nazw roślin — sprawdź sieć.", file=sys.stderr)

    n = write_frozenset_module(
        out_path=OUT,
        const_name="PLANTS_NORMS",
        items=bag,
        doc_first_line=(
            "Flora (pole Roślina): zielonyogrodek.pl (katalog) + atlas-roslin.pl (skorowidz) "
            "+ en.wikipedia."
        ),
        generator_script="scripts/build_plants_bs4.py",
    )
    print(f"Zapisano {n} wpisów → {OUT}")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as e:
        print(f"Błąd HTTP: {e}", file=sys.stderr)
        sys.exit(1)
