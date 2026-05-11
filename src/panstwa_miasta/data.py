"""Runtime dictionaries used for answer validation.

Source of truth:

* ``COUNTRIES``  -> SQL table ``countries`` (seeded from
  :mod:`panstwa_miasta.countries_seed`). The set below is just an in-memory
  cache populated by :func:`reload_countries` after the database is
  initialised. Importing this module before :func:`db.init_db` runs is fine
  -- ``COUNTRIES`` will simply be empty until the first reload.
* ``NAMES``      -> SQL table ``names`` (seeded from :mod:`panstwa_miasta.names_seed`).
* ``JOBS``       -> SQL table ``jobs`` (seeded from :mod:`panstwa_miasta.jobs_seed`).
  Regeneracja modułu seed: ``uv run python scripts/build_jobs_seed.py --zawody … --liniowy …``.

In-memory caches are filled by the FastAPI lifespan handler (and pytest
fixtures via :func:`db.init_db`).
"""

from __future__ import annotations

COUNTRIES: set[str] = set()
NAMES: set[str] = set()
JOBS: set[str] = set()

# Alias: dla wielowyrazowych zawodów dodajemy pierwsze słowo (>3 znaki) jako
# osobny wpis w zbiorze — tak jak wcześniej przy ``zawody.txt``.
JOB_ALIAS_PREFIX_SKIP = frozenset({"akredytowany", "pomocniczy"})


async def reload_countries() -> None:
    """Refresh ``COUNTRIES`` from the SQL ``countries`` table.

    Mutates the existing set in place so callers that already hold a
    reference (e.g. ``from panstwa_miasta.data import COUNTRIES``) keep
    seeing the up-to-date view.
    """
    from .db import load_country_norms

    norms = await load_country_norms()
    COUNTRIES.clear()
    COUNTRIES.update(norms)


async def reload_names() -> None:
    """Refresh ``NAMES`` from the SQL ``names`` table."""
    from .db import load_name_norms

    norms = await load_name_norms()
    NAMES.clear()
    NAMES.update(norms)


async def reload_jobs() -> None:
    """Odświeża ``JOBS`` z tabeli ``jobs`` + aliasy pierwszego słowa."""
    from .db import load_job_norms

    norms = await load_job_norms()
    JOBS.clear()
    for n in norms:
        JOBS.add(n)
        words = n.split()
        if len(words) >= 2:
            head = words[0]
            if len(head) > 3 and head not in JOB_ALIAS_PREFIX_SKIP:
                JOBS.add(head)
