"""Jednorazowy helper: ekstrakcja surowych nazw zawodow z hierarchii PKD/ZRSZ.

Wejscie:  JSON hierarchiczny (np. pobrany z API ZRSZ) — podaj ścieżką.
Wyjscie:  domyślnie ``scripts/pkd_raw_jobs.txt`` (gitignored).

Po wygenerowaniu można curować wpisy do ``src/panstwa_miasta/jobs_seed.py``.

Uruchomienie z roota repo:
    uv run python scripts/extract_jobs.py --src /sciezka/do/hierarchiczny.json
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DST = ROOT / "scripts" / "pkd_raw_jobs.txt"


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
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True, help="hierarchiczny.json z ZRSZ")
    ap.add_argument("--out", type=Path, default=DEFAULT_DST, help="plik wyjściowy z nazwami")
    args = ap.parse_args()
    if not args.src.is_file():
        raise SystemExit(f"Brak pliku źródłowego: {args.src}")
    with args.src.open(encoding="utf-8") as fh:
        data = json.load(fh)
    result: set[str] = set()
    extract_opis(data, result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for opis in sorted(result):
            f.write(opis + "\n")
    print(f"Zapisano {len(result)} unikalnych nazw zawodow do {args.out}.")


if __name__ == "__main__":
    main()
