#!/usr/bin/env python3
"""CLI inbox for dictionary suggestions from post-game appeals."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from panstwa_miasta.db import (
    fetch_dictionary_suggestion,
    list_dictionary_suggestions,
    set_dictionary_suggestion_status,
)

_SEED_HINTS: dict[str, str] = {
    "countries": "src/panstwa_miasta/countries_seed.py",
    "cities": "src/panstwa_miasta/cities_seed*.py / scripts regeneracji miast",
    "names": "src/panstwa_miasta/names_seed.py",
    "jobs": "src/panstwa_miasta/jobs_seed.py (ew. scripts/build_jobs_seed.py)",
    "animals": "src/panstwa_miasta/animals_seed_generated.py",
    "plants": "src/panstwa_miasta/plants_seed_generated.py",
}


def _format_row(row: dict) -> str:
    return (
        f"#{row['id']} [{row['status']}] {row['category']} "
        f"«{row['proposed_display']}» pokój={row['room_id']} runda={row['round']} "
        f"litera={row['letter']} gracz={row['player_name']}"
    )


async def cmd_list(_: argparse.Namespace) -> int:
    rows = await list_dictionary_suggestions("pending")
    if not rows:
        print("Brak oczekujących propozycji.")
        return 0
    for row in rows:
        print(_format_row(row))
    return 0


async def cmd_show(args: argparse.Namespace) -> int:
    row = await fetch_dictionary_suggestion(args.suggestion_id)
    if row is None:
        print(f"Nie znaleziono propozycji #{args.suggestion_id}.", file=sys.stderr)
        return 1
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


async def cmd_approve(args: argparse.Namespace) -> int:
    row = await fetch_dictionary_suggestion(args.suggestion_id)
    if row is None:
        print(f"Nie znaleziono propozycji #{args.suggestion_id}.", file=sys.stderr)
        return 1
    ok = await set_dictionary_suggestion_status(
        args.suggestion_id,
        "approved",
        review_note=args.note,
    )
    if not ok:
        print("Nie udało się zaktualizować statusu.", file=sys.stderr)
        return 1
    target = str(row.get("target_seed") or "")
    hint = _SEED_HINTS.get(target, "odpowiedni plik seeda dla kategorii")
    print(f"Zatwierdzono #{args.suggestion_id}. Ręcznie dopisz do: {hint}")
    print(f"Proponowany wpis: {row.get('proposed_display')!r} (norm: {row.get('proposed_norm')!r})")
    return 0


async def cmd_reject(args: argparse.Namespace) -> int:
    ok = await set_dictionary_suggestion_status(
        args.suggestion_id,
        "rejected",
        review_note=args.note,
    )
    if not ok:
        print(f"Nie znaleziono propozycji #{args.suggestion_id}.", file=sys.stderr)
        return 1
    print(f"Odrzucono #{args.suggestion_id}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Moderacja propozycji słownika z odwołań po grze.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Lista oczekujących propozycji")

    show = sub.add_parser("show", help="Pełny rekord propozycji")
    show.add_argument("suggestion_id", type=int)

    approve = sub.add_parser("approve", help="Oznacz jako zatwierdzoną (bez auto-merge seedów)")
    approve.add_argument("suggestion_id", type=int)
    approve.add_argument("--note", default=None)

    reject = sub.add_parser("reject", help="Odrzuć propozycję")
    reject.add_argument("suggestion_id", type=int)
    reject.add_argument("--note", default=None)

    return parser


async def _main_async(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "list":
        return await cmd_list(args)
    if args.command == "show":
        return await cmd_show(args)
    if args.command == "approve":
        return await cmd_approve(args)
    if args.command == "reject":
        return await cmd_reject(args)
    parser.error(f"unknown command: {args.command}")
    return 2


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main_async(argv if argv is not None else sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
