"""Migruje istniejącą bazę SQLite: wypełnia ``jobs.kod`` + dodaje nowe zawody z KZiS.

Uruchom::

    uv run python scripts/migrate_jobs_kzis.py [--db scieżka/panstwa_miasta.db]
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

# Dodajemy src do ścieżki, żeby zaimportować seed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from panstwa_miasta.db import _name_norm  # noqa: E402
from panstwa_miasta.jobs_seed import JOBS_SEED  # noqa: E402


def _migrate(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.execute("SELECT COUNT(*) FROM jobs")
    before = cur.fetchone()[0]

    updated = 0
    inserted = 0
    new_norms: set[str] = set()

    for row in JOBS_SEED:
        opis_norm = _name_norm(row["opis"])
        kod = row["kod"]

        if kod:
            cur = conn.execute(
                "UPDATE jobs SET kod = ? WHERE opis_norm = ? AND (kod IS NULL OR kod = '')",
                (kod, opis_norm),
            )
            updated += cur.rowcount

        # Insert new jobs not yet in the table
        if opis_norm not in new_norms:
            new_norms.add(opis_norm)
            cur = conn.execute(
                "INSERT OR IGNORE INTO jobs (kod, opis, opis_norm) VALUES (?, ?, ?)",
                (kod, row["opis"], opis_norm),
            )
            inserted += cur.rowcount

    conn.commit()
    cur = conn.execute("SELECT COUNT(*) FROM jobs")
    after = cur.fetchone()[0]
    conn.close()

    print(f"Przed: {before} wierszy")
    print(f"Zaktualizowano kodów: {updated}")
    print(f"Wstawiono nowych: {inserted}")
    print(f"Po: {after} wierszy")


def main() -> None:
    ap = argparse.ArgumentParser(description="Migruje jobs.kod + nowe zawody z KZiS.")
    ap.add_argument(
        "--db",
        type=Path,
        default=Path("panstwa_miasta.db"),
        help="Ścieżka do bazy SQLite (domyślnie panstwa_miasta.db)",
    )
    args = ap.parse_args()

    if not args.db.is_file():
        raise SystemExit(f"Brak pliku bazy: {args.db}")

    _migrate(args.db)


if __name__ == "__main__":
    main()
