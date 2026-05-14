#!/usr/bin/env python3
"""Wypisz COUNT(*) dla tabel — porównanie SQLite vs Turso przed cutover."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from panstwa_miasta.db_backend import connect

_TABLES = (
    "countries",
    "cities",
    "names",
    "jobs",
    "rooms",
    "players",
    "game_transcripts",
    "dictionary_suggestions",
)


async def _counts() -> dict[str, int]:
    out: dict[str, int] = {}
    async with connect() as db:
        for table in _TABLES:
            async with db.execute(f"SELECT COUNT(*) FROM {table}") as cur:
                row = await cur.fetchone()
            out[table] = int(row[0]) if row else 0
    return out


async def _run(_: argparse.Namespace) -> int:
    data = await _counts()
    json.dump(data, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    return asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
