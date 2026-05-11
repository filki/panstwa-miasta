"""Runtime dictionaries used for answer validation.

Source of truth:

* ``COUNTRIES``  -> SQL table ``countries`` (seeded from
  :mod:`panstwa_miasta.countries_seed`). The set below is just an in-memory
  cache populated by :func:`reload_countries` after the database is
  initialised. Importing this module before :func:`db.init_db` runs is fine
  -- ``COUNTRIES`` will simply be empty until the first reload.
* ``NAMES``      -> SQL table ``names`` (seeded from :mod:`panstwa_miasta.names_seed`).
  The set is an in-memory cache filled by :func:`reload_names` after
  :func:`db.init_db` runs.
* ``JOBS``       -> ``data/*.txt`` (currently ``zawody.txt``) with a smart
  first-word alias for multi-word PKD entries.
"""

import pathlib

COUNTRIES: set[str] = set()
NAMES: set[str] = set()


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


# Dynamiczne ścieżki do plików danych
base_path = pathlib.Path(__file__).parent.parent.parent
data_dir = base_path / "data"

# Ladowanie zawodow z curated zawody.txt.
#
# Historia bledu: wczesniej rozbijalismy kazda linie na slowa >3 znaki, co
# wpychalo do JOBS smieci typu "spraw" / "specjalista" / "ofert" (z PKD-owych
# wielowyrazowych nazw w surowym raw_jobs.txt). raw_jobs.txt zniknal z repo,
# a tu zostawiamy pelne frazy plus jeden bezpieczny alias.
#
# Alias: dla N-wyrazowych entries dodajemy pierwsze slowo (>3 znakow) jako
# pojedynczy zawod -- zeby gracz wpisujacy "agent" trafial w zbior, gdy w
# zawody.txt jest tylko "agent celny", "agent klarujacy" itd. Pierwsze slowo
# w PKD jest niemal zawsze rzeczownikiem glownym (lekarz, agent, analityk),
# z wyjatkiem nielicznych entries zaczynajacych sie od przymiotnika
# kwalifikujacego -- te pomijamy.
JOB_ALIAS_PREFIX_SKIP = frozenset({"akredytowany", "pomocniczy"})

JOBS = set()
for txt_file in data_dir.glob("*.txt"):
    try:
        with open(txt_file, encoding="utf-8") as f:
            for line in f:
                job = line.strip().lower()
                if not job:
                    continue
                JOBS.add(job)
                words = job.split()
                if len(words) >= 2:
                    head = words[0]
                    if len(head) > 3 and head not in JOB_ALIAS_PREFIX_SKIP:
                        JOBS.add(head)
        print(f"OK Zaladowano zawody z pliku: {txt_file.name}")
    except Exception as e:
        print(f"BLAD podczas ladowania zawodow {txt_file.name}: {e}")
