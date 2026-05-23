"""Wspólne narzędzia dla skryptów generujących ``*_seed_generated.py``."""

from __future__ import annotations

import time
from pathlib import Path


def norm_game(s: str) -> str:
    """Jak ``panstwa_miasta.manager.normalize_text``."""
    s = s.strip().lower().replace("-", " ")
    while "  " in s:
        s = s.replace("  ", " ")
    return s


def write_frozenset_module(
    *,
    out_path: Path,
    const_name: str,
    items: set[str],
    doc_first_line: str,
    generator_script: str,
) -> int:
    """Zapisuje moduł z jednym ``frozenset``. Zwraca liczbę wpisów."""

    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace('"', '\\"')

    sorted_items = sorted(items, key=lambda x: (x.casefold(), x))
    body = "\n".join(f'    "{esc(i)}",' for i in sorted_items)
    content = f'''"""{doc_first_line}

Wygenerowano skryptem ``{generator_script}``. Nie edytuj ręcznie — odtwórz skryptem.
"""

from __future__ import annotations

from typing import Final

{const_name}: Final[frozenset[str]] = frozenset({{
{body}
}})
'''
    out_path.write_text(content, encoding="utf-8")
    return len(sorted_items)


def polite_sleep(seconds: float = 0.35) -> None:
    time.sleep(seconds)
