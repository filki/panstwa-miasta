#!/usr/bin/env python3
"""Pobiera z polskiej Wikipedii (API) artykuły z drzew kategorii „Miasta …” / „Miejscowości …”.

Dla każdej litery (np. A, B) masz mapę ``Kategoria:…`` → ``kraj`` jak w ``countries_seed.name``.
Wynik: ``src/panstwa_miasta/cities_seed_<litera>_generated.py``.

Uruchom z katalogu głównego repozytorium:

    uv run python scripts/build_cities_from_plwiki.py A
    uv run python scripts/build_cities_from_plwiki.py B

Między zapytaniami jest przerwa (domyślnie 2,2 s), żeby uniknąć HTTP 429.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

from panstwa_miasta.city_name_rules import keep_city_name_for_pl_game

UA = "PanstwaMiasta/1.0 (+https://github.com; cities seed rebuild; Python-urllib)"
REQUEST_DELAY_S = 2.2
API = "https://pl.wikipedia.org/w/api.php"
REPO_ROOT = Path(__file__).resolve().parents[1]

# Litera → (kategoria główna pl.wiki → ``kraj`` jak ``countries_seed.name``)
LETTER_ROOTS: dict[str, dict[str, str]] = {
    "A": {
        "Kategoria:Miasta w Abchazji": "Abchazja",
        "Kategoria:Miasta w Afganistanie": "Afganistan",
        "Kategoria:Miasta w Albanii": "Albania",
        "Kategoria:Miasta w Algierii": "Algieria",
        "Kategoria:Miasta w Andorze": "Andora",
        "Kategoria:Miasta w Angoli": "Angola",
        "Kategoria:Miasta w Antigui i Barbudzie": "Antigua i Barbuda",
        "Kategoria:Miasta w Arabii Saudyjskiej": "Arabia Saudyjska",
        "Kategoria:Miasta w Argentynie": "Argentyna",
        "Kategoria:Miasta w Armenii": "Armenia",
        "Kategoria:Miasta w Australii": "Australia",
        "Kategoria:Miasta w Austrii": "Austria",
        "Kategoria:Miasta w Azerbejdżanie": "Azerbejdżan",
    },
    "B": {
        "Kategoria:Miasta Bahamów": "Bahamy",
        "Kategoria:Miasta w Bahrajnie": "Bahrajn",
        "Kategoria:Miasta w Bangladeszu": "Bangladesz",
        "Kategoria:Miasta Barbadosu": "Barbados",
        "Kategoria:Miasta w Belgii": "Belgia",
        "Kategoria:Miasta w Belize": "Belize",
        "Kategoria:Miasta Beninu": "Benin",
        "Kategoria:Miasta Bhutanu": "Bhutan",
        "Kategoria:Miasta na Białorusi": "Białoruś",
        "Kategoria:Miasta w Boliwii": "Boliwia",
        "Kategoria:Miasta w Bośni i Hercegowinie": "Bośnia i Hercegowina",
        "Kategoria:Miasta Botswany": "Botswana",
        "Kategoria:Miasta w Brazylii": "Brazylia",
        "Kategoria:Miasta Brunei": "Brunei",
        "Kategoria:Miasta w Bułgarii": "Bułgaria",
        "Kategoria:Miasta w Burkina Faso": "Burkina Faso",
        "Kategoria:Miasta w Burundi": "Burundi",
    },
}

# Podkategorie meta — bez „Miasta na …” (np. Białoruś: ``Kategoria:Miasta na Białorusi``).
SKIP_SUBCAT_PREFIXES: tuple[str, ...] = (
    "Kategoria:Miasta według",
    "Kategoria:Miasta alfabetycznie",
    "Kategoria:Miasta według ludności",
    "Kategoria:Miasta portowe",
    "Kategoria:Miasta partnerskie",
    "Kategoria:Miasta UNESCO",
)

SKIP_PAGE_PREFIXES: tuple[str, ...] = (
    "Miasta w ",
    "Miejscowości w ",
    "Lista miast",
    "Lista ",
    "Miasto statutarne",
    "Dawne miasta",
)


def _http_get(params: dict[str, str]) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(5):
        try:
            time.sleep(REQUEST_DELAY_S)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 4:
                wait = 30 * (attempt + 1)
                print(f"  HTTP {e.code}, czekam {wait}s…")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")


def _category_members(cmtitle: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    cont: dict[str, str] = {}
    while True:
        q: dict[str, str] = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": cmtitle,
            "cmlimit": "500",
            "cmtype": "page|subcat",
        }
        q.update(cont)
        data = _http_get(q)
        for m in data.get("query", {}).get("categorymembers", []):
            out.append((int(m["ns"]), str(m["title"])))
        cont = data.get("continue", {})
        if "cmcontinue" not in cont:
            break
        cont = {"cmcontinue": cont["cmcontinue"]}
    return out


def _skip_subcat(title: str) -> bool:
    return any(title.startswith(p) for p in SKIP_SUBCAT_PREFIXES)


def _skip_page(title: str) -> bool:
    return any(title.startswith(p) for p in SKIP_PAGE_PREFIXES)


def _clean_city_title(title: str, kraj: str) -> str:
    t = title.strip()
    t = re.sub(r" \(miasto\)$", "", t, flags=re.IGNORECASE)
    esc = re.escape(f" ({kraj})")
    t = re.sub(esc + r"$", "", t)
    return t


def crawl_country(root_cat: str, kraj: str) -> set[str]:
    seen_cats: set[str] = set()
    cities: set[str] = set()
    q: deque[str] = deque([root_cat])

    while q:
        cat = q.popleft()
        if cat in seen_cats:
            continue
        seen_cats.add(cat)

        members = _category_members(cat)
        for ns, title in members:
            if ns == 14:
                if title in seen_cats or _skip_subcat(title):
                    continue
                q.append(title)
            elif ns == 0:
                if _skip_page(title):
                    continue
                cities.add(_clean_city_title(title, kraj))
    return cities


def main(letter: str) -> None:
    letter = letter.strip().upper()
    roots = LETTER_ROOTS.get(letter)
    if not roots:
        print(
            f"Brak mapy dla litery {letter!r}. Dostępne: {', '.join(sorted(LETTER_ROOTS))}",
            file=sys.stderr,
        )
        sys.exit(1)

    out_path = REPO_ROOT / "src" / "panstwa_miasta" / f"cities_seed_{letter.lower()}_generated.py"
    const = f"CITIES_SEED_{letter}_WIKI"

    rows: list[tuple[str, str]] = []
    for root, kraj in sorted(roots.items(), key=lambda x: x[1]):
        print(root, "→", kraj)
        names = crawl_country(root, kraj)
        print(f"  zebrano {len(names)} nazw")
        for n in sorted(names, key=lambda s: (s.casefold(), s)):
            rows.append((n, kraj))

    dedup: dict[tuple[str, str], None] = {}
    for n, k in rows:
        if not keep_city_name_for_pl_game(n):
            continue
        dedup[(n, k)] = None
    rows_unique = sorted(dedup.keys(), key=lambda t: (t[1].casefold(), t[0].casefold()))

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    body_lines = [f'    ("{esc(n)}", "{esc(k)}"),' for n, k in rows_unique]

    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    script_name = "scripts/build_cities_from_plwiki.py"
    content = f'''"""Miasta z polskiej Wikipedii — kraje na literę {letter}.

Wygenerowano automatycznie: {stamp}
Źródło: ``{script_name} {letter}`` (MediaWiki API, rekurencyjnie podkategorie).
Pominięto wpisy spoza ``panstwa_miasta.city_name_rules`` (polski alfabet + dozwolone znaki).

Nie edytuj ręcznie — odtwórz skryptem po zmianie logiki lub odświeżeniu danych.
"""

from __future__ import annotations

from typing import Final

# (nazwa wyświetlana / odpowiedź gracza, kraj jak w ``countries_seed``)
{const}: Final[list[tuple[str, str]]] = [
{chr(10).join(body_lines)}
]
'''
    out_path.write_text(content, encoding="utf-8")
    print(f"Zapisano {len(rows_unique)} wpisów → {out_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Zbuduj cities_seed_<litera>_generated.py z pl.wikipedia."
    )
    p.add_argument("letter", help="Litera (np. A, B)")
    args = p.parse_args()
    main(args.letter)
