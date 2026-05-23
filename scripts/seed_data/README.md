# Słowniki statyczne (JSONL.gz)

Pliki w tym katalogu zastępują wielkie moduły ``*_generated.py`` w ``src/``.

| Plik | Zawartość | Odtwarzanie |
|------|-----------|-------------|
| `animals_norms.jsonl.gz` | normy zwierząt (wiki + GBIF) | `build_animals_wikipedia_bs4.py` + opcjonalnie GBIF, potem `export_norms_seed_data.py` |
| `plants_norms.jsonl.gz` | normy roślin | `build_plants_bs4.py` + GBIF, potem export |
| `cities_geonames.jsonl.gz` | miasta GeoNames (poza PL) | `build_cities_from_geonames.py`, potem `apply_official_pl_city_names.py` |

Po zmianie źródeł:

```bash
uv run python scripts/build_cities_from_geonames.py   # wymaga scripts/cities15000.txt
uv run python scripts/apply_official_pl_city_names.py
uv run python scripts/export_norms_seed_data.py      # po przebudowie fauna/flora z wiki
```

``init_db()`` ładuje te pliki do SQLite/Turso, gdy tabele są puste.
