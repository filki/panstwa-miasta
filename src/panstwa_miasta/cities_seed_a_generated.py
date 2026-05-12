"""Miasta z polskiej Wikipedii — kraje na literę A.

Odtwórz listę skryptem (wymaga sieci, przerwy między zapytaniami)::

    uv run python scripts/build_cities_from_plwiki.py A

Do czasu odbudowy moduł ma pustą listę — gra ładuje miasta z PL (Wikidata) i GeoNames.
"""

from __future__ import annotations

from typing import Final

CITIES_SEED_A_WIKI: Final[list[tuple[str, str]]] = []
