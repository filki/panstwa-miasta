"""Agregator danych seed dla miast.

Kolejność:

1. **Polska** — Wikidata (``cities_seed_pl_generated`` / ``build_polish_cities_wikidata.py``).
2. **Inne kraje, litera A** — polska Wikipedia (``cities_seed_a_generated`` / ``build_cities_from_plwiki.py``).
3. **Reszta świata** — GeoNames ``cities15000`` z progiem populacji (domyślnie ≥ 15 000),
   bez PL (``cities_seed_geonames_generated`` / ``build_cities_from_geonames.py``).

``init_db()`` robi ``INSERT OR IGNORE`` do tabeli ``cities`` (unikalność po ``nazwa_norm``,
``kraj_norm``).
"""

from .cities_seed_a_generated import CITIES_SEED_A_WIKI
from .cities_seed_geonames_generated import CITIES_SEED_GEONAMES
from .cities_seed_pl_generated import CITIES_SEED_PL_WIKI

# Konwersja krotek (nazwa, kraj) na słowniki oczekiwane przez db.py
CITIES_SEED = [
    {"nazwa": row[0], "kraj": row[1]}
    for row in (*CITIES_SEED_PL_WIKI, *CITIES_SEED_A_WIKI, *CITIES_SEED_GEONAMES)
]
