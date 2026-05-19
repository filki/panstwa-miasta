"""Buduje ``src/panstwa_miasta/jobs_seed.py`` z listy zawodów + JSON PKD (liniowy).

Gra ładuje zawody wyłącznie z SQLite (seed ``jobs_seed.py``). Ten skrypt jest
tylko do regeneracji modułu seed — ścieżki wejściowe podajesz explicite.

Przykład (z kodami PKD, jeśli masz JSON liniowy):
    uv run python scripts/build_jobs_seed.py --zawody data/zawody.txt --liniowy /tmp/liniowy.json

Tylko lista zawodów (wszystkie ``kod`` = ``None``):
    uv run python scripts/build_jobs_seed.py --zawody data/zawody.txt
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "src" / "panstwa_miasta" / "jobs_seed.py"

_WS = re.compile(r"\s+")


def fold(s: str) -> str:
    s = s.strip().lower().replace("-", " ").replace("/", " ")
    s = _WS.sub(" ", s)
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _load_pkd(path: Path) -> list[tuple[str, str, str]]:
    rows = json.loads(path.read_text(encoding="utf-8")).get("pozycje") or []
    out: list[tuple[str, str, str]] = []
    for r in rows:
        kod = r.get("kod") or ""
        if len(kod) != 6:
            continue
        opis = (r.get("opis") or "").strip()
        if opis:
            out.append((kod, opis, fold(opis)))
    return out


def _best_kod(line: str, pkd: list[tuple[str, str, str]]) -> str:
    jf = fold(line)
    if not jf:
        return ""
    exact: list[str] = []
    substr: list[tuple[int, str]] = []
    j_tokens = [t for t in jf.split() if len(t) > 2]
    token_hits: list[tuple[int, str]] = []
    for kod, _raw, of in pkd:
        if jf == of:
            exact.append(kod)
        elif jf in of or (of in jf and len(of) >= 8):
            substr.append((len(of), kod))
        else:
            hit = sum(1 for t in j_tokens if t in of)
            if hit and len(j_tokens):
                token_hits.append((hit, kod))
    if exact:
        return sorted(exact)[0]
    if substr:
        substr.sort(key=lambda x: (x[0], x[1]))
        return substr[0][1]
    if token_hits:
        token_hits.sort(key=lambda x: (-x[0], x[1]))
        best = token_hits[0][0]
        return sorted(k for s, k in token_hits if s == best)[0]
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Generuje jobs_seed.py z plików lokalnych.")
    ap.add_argument("--zawody", type=Path, required=True, help="Tekst: jedna nazwa zawodu na linię")
    ap.add_argument(
        "--liniowy",
        type=Path,
        default=None,
        help="Opcjonalnie: JSON PKD liniowy (pozycje[]) — dopasowanie kodów PKD",
    )
    ap.add_argument(
        "--add-new",
        action="store_true",
        default=False,
        help="Dodaj nowe zawody z KZiS, które nie pasują do żadnego z --zawody",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Ścieżka wyjścia (domyślnie {DEFAULT_OUT})",
    )
    args = ap.parse_args()

    if not args.zawody.is_file():
        raise SystemExit(f"Brak pliku --zawody: {args.zawody}")
    if args.liniowy is not None and not args.liniowy.is_file():
        raise SystemExit(f"Brak pliku --liniowy: {args.liniowy}")

    pkd = _load_pkd(args.liniowy) if args.liniowy else []
    seen: set[str] = set()
    lines: list[str] = []
    for raw in args.zawody.read_text(encoding="utf-8").splitlines():
        opis = raw.strip()
        if not opis or opis in seen:
            continue
        seen.add(opis)
        lines.append(opis.lower())

    # Track which KZiS entries are matched, so we can add unmatched ones later
    matched_kzis: set[str] = set()

    body: list[str] = []
    for opis in lines:
        kod = _best_kod(opis, pkd)
        if kod:
            matched_kzis.add(kod)
            body.append(f'    {{"opis": {repr(opis)}, "kod": {repr(kod)}}},')
        else:
            body.append(f'    {{"opis": {repr(opis)}, "kod": None}},')

    # Add new jobs from KZiS that weren't matched by any seed entry
    new_count = 0
    if args.add_new and pkd:
        for kod, raw_opis, _of in pkd:
            if kod in matched_kzis:
                continue
            # Skip "Pozostali..." entries (kod ending in 90) — too generic for gameplay
            if kod.endswith("90"):
                continue
            opis = raw_opis.strip().lower()
            if opis in seen:
                continue
            seen.add(opis)
            body.append(f'    {{"opis": {repr(opis)}, "kod": {repr(kod)}}},')
            new_count += 1

    body.sort()  # keep sorted for deterministic diffs

    content = f'''"""Seed data for the ``jobs`` SQL table.

Wygenerowano przez ``scripts/build_jobs_seed.py``. Opcjonalnie z JSON PKD
liniowym (``--liniowy``). Edytuj wiersze tutaj — ``init_db()`` robi ``INSERT OR IGNORE``.
"""

from __future__ import annotations

from typing import Final, TypedDict


class JobSeed(TypedDict):
    """Jedna pozycja słownika zawodów (tekst gry + opcjonalny kod PKD)."""

    opis: str
    kod: str | None


JOBS_SEED: Final[list[JobSeed]] = [
{chr(10).join(body)}
]
'''
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(content, encoding="utf-8")
    print(
        f"Zapisano {len(lines) + new_count} pozycji ({len(lines)} z seeda + {new_count} nowych z KZiS) do {args.out.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
