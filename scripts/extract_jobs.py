"""Jednorazowy helper: ekstrakcja surowych nazw zawodow z hierarchii PKD/ZRSZ.

Wejscie:  data/hierarchiczny.json  (pobrany recznie z API ZRSZ /
                                    Klasyfikacji Zawodow i Specjalnosci;
                                    NIE jest trackowany w gicie -- zbyt duzy
                                    i wlasciwie zawsze regenerowalny)
Wyjscie:  data/raw_jobs.txt        (intermediate; tez nietrackowany)

Po wygenerowaniu raw_jobs.txt curacja odbywa sie recznie do
data/zawody.txt (juz w gicie) -- patrz README sekcja "Dane slownikowe".

Uruchomienie z roota repo:
    python scripts/extract_jobs.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "hierarchiczny.json"
DST = ROOT / "data" / "raw_jobs.txt"


def extract_opis(obj, result):
    if isinstance(obj, dict):
        if "opis" in obj:
            result.add(obj["opis"])
        for _k, v in obj.items():
            extract_opis(v, result)
    elif isinstance(obj, list):
        for item in obj:
            extract_opis(item, result)


def main() -> None:
    if not SRC.exists():
        raise SystemExit(
            f"Brak pliku zrodlowego {SRC}. Pobierz go recznie z API ZRSZ "
            "(Klasyfikacja Zawodow i Specjalnosci) i polozyc w data/."
        )
    with SRC.open(encoding="utf-8") as fh:
        data = json.load(fh)
    result: set[str] = set()
    extract_opis(data, result)
    with DST.open("w", encoding="utf-8") as f:
        for opis in sorted(result):
            f.write(opis + "\n")
    print(f"Zapisano {len(result)} unikalnych nazw zawodow do {DST}.")


if __name__ == "__main__":
    main()
