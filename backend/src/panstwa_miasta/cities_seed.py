"""Agregator danych seed dla miast.

1. **Polska** — ``cities_seed_pl_generated`` (Wikidata).
2. **GeoNames** — ``scripts/seed_data/cities_geonames.jsonl.gz`` (eksport:
   ``scripts/export_norms_seed_data.py`` po ``build_cities_from_geonames.py``).

``init_db()`` wstawia do tabeli ``cities`` tylko gdy pusta.
"""

from .cities_seed_pl_generated import CITIES_SEED_PL_WIKI
from .seed_data_loader import load_cities_geonames_from_seed_file

# Konwersja krotek (nazwa, kraj) na słowniki oczekiwane przez db.py
CITIES_SEED = [
    {"nazwa": row[0], "kraj": row[1]}
    for row in (*CITIES_SEED_PL_WIKI, *load_cities_geonames_from_seed_file())
]
