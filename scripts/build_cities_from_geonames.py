#!/usr/bin/env python3
"""Buduje ``cities_seed_geonames_generated.py`` z pliku GeoNames ``cities15000.txt``.

Źródło pliku: https://download.geonames.org/export/dump/cities15000.zip (format TSV,
opis pól w ``readme.txt`` w tym samym katalogu).

- **Polska (PL)** jest pomijana — miasta w PL pochodzą z Wikidata
  (``cities_seed_pl_generated`` / ``build_polish_cities_wikidata.py``).
- **Świat**: domyślnie ``population >= 15000`` (``--min-pop``).
- Kraje: ISO-3166-1 alpha-2 → nazwa jak w ``countries_seed`` (JSON
  ``scripts/data/country_iso_pl_umpirsky.json`` + dopiski terytoriów).
- **PPLX** (dzielnice) i podobne są pomijane.
- Nazwa: preferencja zapisów z polskimi znakami z ``alternatenames``;
  dla liter ``vqx`` używane jest ``keep_city_name_for_geonames_seed``.

Uruchom z katalogu głównego repozytorium::

    uv run python scripts/build_cities_from_geonames.py

Opcje::

    uv run python scripts/build_cities_from_geonames.py --min-pop 5000
    uv run python scripts/build_cities_from_geonames.py --input scripts/cities15000.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from panstwa_miasta.city_name_rules import keep_city_name_for_geonames_seed  # noqa: E402
from panstwa_miasta.countries_seed import COUNTRIES_SEED  # noqa: E402

POLISH_MARKERS: frozenset[str] = frozenset("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

ISO_KRAJ_OVERRIDES: dict[str, str] = {
    "CI": "Wybrzeże Kości Słoniowej",
    "ZA": "Południowa Afryka",
    "TW": "Republika Chińska / Tajwan",
    "PS": "Palestyna",
    "MM": "Mjanma",
    "XK": "Kosowo",
    "EH": "Sahara Zachodnia",
    "AS": "Stany Zjednoczone",
    "GU": "Stany Zjednoczone",
    "MP": "Stany Zjednoczone",
    "PR": "Stany Zjednoczone",
    "UM": "Stany Zjednoczone",
    "VI": "Stany Zjednoczone",
    "AI": "Wielka Brytania",
    "BM": "Wielka Brytania",
    "VG": "Wielka Brytania",
    "KY": "Wielka Brytania",
    "MS": "Wielka Brytania",
    "TC": "Wielka Brytania",
    "FK": "Wielka Brytania",
    "GI": "Wielka Brytania",
    "GG": "Wielka Brytania",
    "JE": "Wielka Brytania",
    "IM": "Wielka Brytania",
    "SH": "Wielka Brytania",
    "IO": "Wielka Brytania",
    "AX": "Finlandia",
    "GL": "Dania",
    "FO": "Dania",
    "SJ": "Norwegia",
    "BV": "Norwegia",
    "HM": "Australia",
    "CX": "Australia",
    "CC": "Australia",
    "NF": "Australia",
    "CK": "Nowa Zelandia",
    "NU": "Nowa Zelandia",
    "NC": "Francja",
    "PF": "Francja",
    "WF": "Francja",
    "YT": "Francja",
    "RE": "Francja",
    "GP": "Francja",
    "MQ": "Francja",
    "GF": "Francja",
    "BL": "Francja",
    "MF": "Francja",
    "PM": "Francja",
    "AW": "Holandia",
    "BQ": "Holandia",
    "CW": "Holandia",
    "SX": "Holandia",
    "HK": "Chiny",
    "MO": "Chiny",
}

SKIP_FEATURE_CODES: frozenset[str] = frozenset({"PPLX", "PPLH", "PPLQ", "PPLW"})


def _norm_key(text: str) -> str:
    """Jak ``manager.normalize_text`` / ``db._name_norm``."""
    return text.strip().lower().replace("-", " ").replace("  ", " ")


def _load_iso_pl_names(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iso_to_kraj(
    iso: str,
    admin1: str,
    seed_names: frozenset[str],
    iso_pl: dict[str, str],
) -> str | None:
    if iso == "GE" and admin1 == "02":
        k = "Abchazja"
        return k if k in seed_names else None
    if iso in ISO_KRAJ_OVERRIDES:
        k = ISO_KRAJ_OVERRIDES[iso]
        return k if k in seed_names else None
    pl = iso_pl.get(iso)
    if not pl:
        return None
    if pl in seed_names:
        return pl
    return None


def _looks_like_short_all_caps_code(s: str) -> bool:
    t = s.strip().replace(" ", "")
    return bool(t) and t.isalpha() and t.isupper() and len(t) <= 4


def _pick_city_label(name: str, ascii_name: str, alternames: str) -> str | None:
    def _alt_ok(s: str) -> bool:
        s2 = s.strip()
        if not s2 or len(s2) < 2:
            return False
        if s2 in (name, ascii_name):
            return True
        return s2[0].isupper()

    parts: list[str] = [name, ascii_name]
    parts += [x.strip() for x in alternames.split(",") if x.strip() and _alt_ok(x.strip())]
    seen: set[str] = set()
    ordered: list[str] = []
    for p in parts:
        if p in seen:
            continue
        seen.add(p)
        ordered.append(p)
    valid = [
        c
        for c in ordered
        if keep_city_name_for_geonames_seed(c) and not _looks_like_short_all_caps_code(c)
    ]
    if not valid:
        return None

    def _pm(s: str) -> int:
        return sum(1 for ch in s if ch in POLISH_MARKERS)

    best_pm = max(_pm(s) for s in valid)
    tier = [s for s in valid if _pm(s) == best_pm]
    if best_pm > 0:
        return max(tier, key=len)
    if name in tier:
        return name
    if ascii_name in tier:
        return ascii_name
    min_len = min(len(s) for s in tier)
    short = [s for s in tier if len(s) == min_len]
    for s in ordered:
        if s in short:
            return s
    return short[0]


def _emit_py(rows: list[tuple[str, str]], out: Path, source: str) -> None:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    body_lines = [f'    ("{esc(n)}", "{esc(k)}"),' for n, k in rows]
    content = f'''"""Miasta z GeoNames (``cities15000``) — świat poza PL, populacja ≥ progu skryptu.

Wygenerowano: {stamp}
Źródło pliku: {source}

Polska (PL) pominięta — ``cities_seed_pl_generated`` (Wikidata). Nazwy: preferencja form
z polskimi znakami w ``alternatenames`` (``scripts/build_cities_from_geonames.py``).

Nie edytuj ręcznie — odtwórz skryptem.
"""

from __future__ import annotations

from typing import Final

CITIES_SEED_GEONAMES: Final[list[tuple[str, str]]] = [
{chr(10).join(body_lines)}
]
'''
    out.write_text(content + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build cities_seed_geonames_generated.py")
    ap.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "scripts" / "cities15000.txt",
        help="Ścieżka do cities15000.txt (GeoNames TSV)",
    )
    ap.add_argument(
        "--country-json",
        type=Path,
        default=REPO_ROOT / "scripts" / "data" / "country_iso_pl_umpirsky.json",
        help="ISO alpha-2 → nazwa PL (umpirsky/country-list)",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "src" / "panstwa_miasta" / "cities_seed_geonames_generated.py",
    )
    ap.add_argument(
        "--min-pop",
        type=int,
        default=15000,
        help="Minimalna populacja (kolumna GeoNames indeks 14); domyślnie 15000",
    )
    args = ap.parse_args()

    seed_names = frozenset(c["name"] for c in COUNTRIES_SEED)
    iso_pl = _load_iso_pl_names(args.country_json)

    rows: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    skipped: dict[str, int] = {
        "pl": 0,
        "feat": 0,
        "pop": 0,
        "kraj": 0,
        "label": 0,
        "dup": 0,
    }

    text = args.input.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        t = line.split("\t")
        if len(t) < 19:
            continue
        iso, admin1 = t[8], t[10]
        fcode = t[7]
        if iso == "PL":
            skipped["pl"] += 1
            continue
        if fcode in SKIP_FEATURE_CODES:
            skipped["feat"] += 1
            continue
        try:
            pop = int(t[14])
        except ValueError:
            skipped["pop"] += 1
            continue
        if pop < args.min_pop:
            skipped["pop"] += 1
            continue
        kraj = _iso_to_kraj(iso, admin1, seed_names, iso_pl)
        if not kraj:
            skipped["kraj"] += 1
            continue
        label = _pick_city_label(t[1], t[2], t[3])
        if not label:
            skipped["label"] += 1
            continue
        key = (_norm_key(label), _norm_key(kraj))
        if key in seen:
            skipped["dup"] += 1
            continue
        seen.add(key)
        rows.append((label, kraj))

    rows.sort(key=lambda r: (r[1].lower(), r[0].lower()))
    try:
        src_rel = str(args.input.relative_to(REPO_ROOT))
    except ValueError:
        src_rel = str(args.input)
    _emit_py(rows, args.output, src_rel)
    print(f"Wrote {len(rows)} rows → {args.output}")
    print("Skipped:", skipped)


if __name__ == "__main__":
    main()
