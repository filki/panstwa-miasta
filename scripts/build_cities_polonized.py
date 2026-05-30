#!/usr/bin/env python3
"""Buduje spolonizowany seed miast z GeoNames cities15000 + alternateNamesV2.

1. Czyta geonames/cities15000.txt — raw dane
2. Czyta alternateNamesV2.zip — wyciąga polskie (pl) odpowiedniki
3. Łączy po geonameid → tworzy 2 pliki JSONL.gz:
   - scripts/seed_data/cities_polonized.jsonl.gz — tylko miasta z formą polską
   - scripts/seed_data/cities_to_translate.jsonl.gz — reszta (do ewentualnego tłumaczenia)

Uruchom z katalogu głównego:
    uv run python scripts/build_cities_polonized.py

Wymaga: geonames/cities15000.txt, /tmp/alternateNamesV2.zip
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GEONAMES_DIR = REPO_ROOT / "geonames"
SCRIPTS_DIR = REPO_ROOT / "scripts"

# --- Konfiguracja ---
DEFAULT_CITIES_TSV = GEONAMES_DIR / "cities15000.txt"
DEFAULT_COUNTRY_JSON = SCRIPTS_DIR / "data" / "country_iso_pl_umpirsky.json"
DEFAULT_ALTERNATE_ZIP = Path("/tmp/alternateNamesV2.zip")
DEFAULT_OUT_POLONIZED = SCRIPTS_DIR / "seed_data" / "cities_polonized.jsonl.gz"
DEFAULT_OUT_TRANSLATE = SCRIPTS_DIR / "seed_data" / "cities_to_translate.jsonl.gz"
DEFAULT_MIN_POP = 15000

# Pomijane kody feature (dzielnice itp.)
SKIP_FEATURE_CODES = frozenset({"PPLX", "PPLH", "PPLQ", "PPLW"})

# Dla liter v/q/x — dodatkowa filtracja
POLISH_MARKERS = frozenset("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")

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


def _norm_key(text: str) -> str:
    """Normalizacja jak db._name_norm."""
    return text.strip().lower().replace("-", " ").replace("  ", " ")


def _load_country_names(path: Path) -> dict[str, str]:
    """ISO alpha-2 → nazwa PL (np. 'GB' → 'Wielka Brytania')."""
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
    if pl and pl in seed_names:
        return pl
    return None


def _looks_like_short_all_caps_code(s: str) -> bool:
    t = s.strip().replace(" ", "")
    return bool(t) and t.isalpha() and t.isupper() and len(t) <= 4


def load_polish_alternames(zip_path: Path) -> dict[str, str]:
    """Wczytuje polskie (pl) alternatywne nazwy z alternateNamesV2.zip.
    Zwraca {geonameid: nazwa_polska}. Preferuje isPreferredName=1."""
    result: dict[str, str] = {}
    if not zip_path.exists():
        print(f"  [WARN] {zip_path} nie istnieje — brak polskich nazw z alternateNames")
        return result
    with zipfile.ZipFile(zip_path, "r") as z:
        with z.open("alternateNamesV2.txt") as f:
            for raw in f:
                parts = raw.decode("utf-8").strip().split("\t")
                if len(parts) < 4:
                    continue
                lang = parts[2]
                if lang == "pl":
                    gid = parts[1]
                    alt_name = parts[3]
                    is_pref = parts[4] if len(parts) > 4 else "0"
                    # Preferuj preferred, potem pierwszy znaleziony
                    if gid not in result or is_pref == "1":
                        result[gid] = alt_name
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, default=DEFAULT_CITIES_TSV)
    ap.add_argument("--alternate-zip", type=Path, default=DEFAULT_ALTERNATE_ZIP)
    ap.add_argument("--country-json", type=Path, default=DEFAULT_COUNTRY_JSON)
    ap.add_argument("--out-polonized", type=Path, default=DEFAULT_OUT_POLONIZED)
    ap.add_argument("--out-translate", type=Path, default=DEFAULT_OUT_TRANSLATE)
    ap.add_argument("--min-pop", type=int, default=DEFAULT_MIN_POP)
    args = ap.parse_args()

    # --- Wczytaj kraje ---
    from panstwa_miasta.countries_seed import COUNTRIES_SEED

    seed_names = frozenset(c["name"] for c in COUNTRIES_SEED)
    iso_pl = _load_country_names(args.country_json)

    # --- Wczytaj polskie alternate names ---
    print("Ładowanie polskich alternate names...")
    pl_alts = load_polish_alternames(args.alternate_zip)
    print(f"  Znaleziono {len(pl_alts)} polskich alternate names")

    # --- Przeparsuj cities15000.txt ---
    print(f"Przetwarzanie {args.input}...")
    geoname_to_city: dict[str, tuple[str, str, str, bool]] = {}
    """{geonameid: (name, kraj, fcode, is_polish)}"""

    text = args.input.read_text(encoding="utf-8")
    seen: set[tuple[str, str]] = set()
    counts = {"pl_skip": 0, "feat_skip": 0, "pop_skip": 0, "kraj_skip": 0, "dup_skip": 0}

    for line in text.splitlines():
        if not line.strip():
            continue
        t = line.split("\t")
        if len(t) < 19:
            continue
        geonameid, name, ascii_name, alternames = t[0], t[1], t[2], t[3]
        iso, admin1, fcode = t[8], t[10], t[7]

        if iso == "PL":
            counts["pl_skip"] += 1
            continue
        if fcode in SKIP_FEATURE_CODES:
            counts["feat_skip"] += 1
            continue
        try:
            pop = int(t[14])
        except ValueError:
            counts["pop_skip"] += 1
            continue
        if pop < args.min_pop:
            counts["pop_skip"] += 1
            continue
        kraj = _iso_to_kraj(iso, admin1, seed_names, iso_pl)
        if not kraj:
            counts["kraj_skip"] += 1
            continue

        # Sprawdź czy jest polska nazwa alternatywna
        pl_name = pl_alts.get(geonameid)
        display_name = pl_name if pl_name else name
        is_polish = pl_name is not None

        key = (_norm_key(display_name), _norm_key(kraj))
        if key in seen:
            counts["dup_skip"] += 1
            continue
        seen.add(key)
        geoname_to_city[geonameid] = (display_name, kraj, fcode, is_polish)

    print(f"  Ogółem: {len(geoname_to_city)} miast")
    print(f"  Pominięte: PL={counts['pl_skip']}, feat={counts['feat_skip']}, "
          f"pop={counts['pop_skip']}, kraj={counts['kraj_skip']}, dup={counts['dup_skip']}")

    # --- Podział na polonized / to_translate ---
    polonized: list[tuple[str, str]] = []
    to_translate: list[tuple[str, str]] = []

    for gid, (nazwa, kraj, fcode, is_pl) in geoname_to_city.items():
        # Dodatkowe heurystyki dla "polonized":
        # 1. Ma polską nazwę alternateNames
        # 2. Ma polskie znaki diakrytyczne w nazwie
        has_diacritics = any(c in POLISH_MARKERS for c in nazwa)
        if is_pl or has_diacritics:
            polonized.append((nazwa, kraj))
        else:
            to_translate.append((nazwa, kraj))

    # Sortowanie
    polonized.sort(key=lambda r: (r[1].lower(), r[0].lower()))
    to_translate.sort(key=lambda r: (r[1].lower(), r[0].lower()))

    print(f"\nPolonized: {len(polonized)}")
    print(f"To translate: {len(to_translate)}")

    # --- Zapisz JSONL ---
    import gzip as gzlib

    def _write_jsonl(path: Path, rows: list[tuple[str, str]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzlib.open(str(path), "wt", encoding="utf-8") as f:
            for n, k in rows:
                f.write(json.dumps({"nazwa": n, "kraj": k}, ensure_ascii=False) + "\n")
        return len(rows)

    n_pol = _write_jsonl(args.out_polonized, polonized)
    print(f"Zapisano {n_pol} → {args.out_polonized}")

    n_tr = _write_jsonl(args.out_translate, to_translate)
    print(f"Zapisano {n_tr} → {args.out_translate}")

    # --- Próbki ---
    print("\nPróbki polonized:")
    for n, k in polonized[:15]:
        pl_flag = "✓" if any(c in POLISH_MARKERS for c in n) else " "
        print(f"  [{pl_flag}] {n} ({k})")

    print("\nPróbki to_translate:")
    for n, k in to_translate[:10]:
        print(f"  {n} ({k})")


if __name__ == "__main__":
    main()
