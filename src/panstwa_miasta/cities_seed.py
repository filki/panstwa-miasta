"""Agregator danych seed dla miast.

1. **Polska** — ``cities_seed_pl_generated`` (Wikidata).
2. **Polonized (GeoNames + AlternateNamesV2)** — ``scripts/seed_data/cities_polonized.jsonl.gz``.
3. **To translate** — ``scripts/seed_data/cities_to_translate.jsonl.gz`` (osobna tabela).

``init_db()`` wstawia do tabeli ``cities`` tylko polonized + PL Wiki.
``init_db()`` wstawia do tabeli ``cities_to_translate`` resztę GeoNames.
"""

from .cities_seed_pl_generated import CITIES_SEED_PL_WIKI
from .seed_data_loader import (
    load_cities_polonized_from_seed_file,
    load_cities_to_translate_from_seed_file,
)

# Główna tabela: tylko spolonizowane + polskie
CITIES_SEED = [
    {"nazwa": row[0], "kraj": row[1]}
    for row in (*CITIES_SEED_PL_WIKI, *load_cities_polonized_from_seed_file())
]

# Tabela do tłumaczenia: reszta GeoNames
CITIES_TO_TRANSLATE = [
    {"nazwa": row[0], "kraj": row[1]}
    for row in load_cities_to_translate_from_seed_file()
]
