#!/usr/bin/env python3
"""
Convert KZiS CSV (Klasyfikacja Zawodów i Specjalności) to a JSON file.

Input: CSV with one quoted string per line, e.g.
    "111101     Parlamentarzysta"
    "311204     Technik budownictwaS"

Only lines with a 6-digit code are extracted. The trailing "S" on the
description (meaning "zawód szkolny") is stripped.

Output format: {"pozycje": [{"kod": "111101", "opis": "Parlamentarzysta"}, ...]}
"""

import argparse
import csv
import json
import re
import sys

LINE_PATTERN = re.compile(r"^(\d{6})\s+(.+)$")


def parse_kzis_csv(input_path: str) -> list[dict[str, str]]:
    """Read the KZiS CSV and return a list of {kod, opis} dicts."""
    pozycje: list[dict[str, str]] = []

    with open(input_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue
            raw = row[0].strip()
            match = LINE_PATTERN.match(raw)
            if not match:
                continue

            kod = match.group(1)
            opis = match.group(2).strip()

            # Remove trailing "S" (zawód szkolny) – handle both "opisS" and "opis S"
            if opis.endswith("S"):
                opis = opis[:-1].strip()

            pozycje.append({"kod": kod, "opis": opis})

    return pozycje


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert KZiS CSV to a JSON seed file.")
    parser.add_argument(
        "--out",
        default="scripts/seed_data/kzis_liniowy.json",
        help="Output JSON path (default: scripts/seed_data/kzis_liniowy.json)",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="Klasyfikacja-KZiS-2014-z-póżn.-zm.-_Dz.U.-z-2016-poz.1876_.csv",
        help="Input CSV file path",
    )
    args = parser.parse_args()

    pozycje = parse_kzis_csv(args.input)

    output = {"pozycje": pozycje}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Written {len(pozycje)} pozycje to {args.out}")


if __name__ == "__main__":
    main()
