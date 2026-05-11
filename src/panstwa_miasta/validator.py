from typing import Any

import httpx

# Logger import
from .logger import get_logger

logger = get_logger(__name__)


class WikipediaValidator:
    def __init__(self):
        self.cache: dict[str, bool] = {}
        self.client = httpx.AsyncClient(timeout=5.0)
        logger.info("WikipediaValidator initialized.")

    async def _search_wikidata(self, term: str) -> str | None:
        """Searches for an entity on Wikidata and returns its ID if a label matches."""
        params = {"action": "wbsearchentities", "search": term, "language": "pl", "format": "json"}
        response = await self.client.get("https://www.wikidata.org/w/api.php", params=params)
        data = response.json()
        for result in data.get("search", []):
            if result.get("label", "").lower() == term:
                return result["id"]
        return None

    async def _get_claims(self, entity_id: str) -> dict[str, list[Any]]:
        """Fetches claims for a given Wikidata entity."""
        params = {"action": "wbgetentities", "ids": entity_id, "props": "claims", "format": "json"}
        response = await self.client.get("https://www.wikidata.org/w/api.php", params=params)
        data = response.json()
        return data.get("entities", {}).get(entity_id, {}).get("claims", {})

    def _check_category(self, claims: dict[str, list[Any]], category: str) -> bool:
        """Checks if any P31 (instance of) claim matches the target category."""
        category_map = {
            "Miasto": {"Q515", "Q1549591", "Q5119"},  # city, town, village
            "Zwierzę": {"Q729", "Q16521"},  # animal, organism
            "Roślina": {"Q756"},  # plant
        }
        if category not in category_map:
            return True

        p31_claims = claims.get("P31", [])
        for claim in p31_claims:
            mainsnak = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id")
            if mainsnak in category_map[category]:
                return True
        return False

    async def validate(self, term: str, category: str) -> bool:
        """
        Sprawdza czy dany termin istnieje w Wikidata i pasuje do kategorii.
        """
        term = term.strip().lower()
        if not term:
            return False

        cache_key = f"{category}:{term}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            entity_id = await self._search_wikidata(term)
            if not entity_id:
                self.cache[cache_key] = False
                return False

            logger.info(f"Entity found for {term}: {entity_id}")
            claims = await self._get_claims(entity_id)
            found = self._check_category(claims, category)

            self.cache[cache_key] = found
            logger.info(f"Validation result for {term} in {category}: {found}")
            return found
        except Exception as e:
            logger.error(f"⚠️ Błąd walidacji Wikidata dla {term}: {e}")
            return True  # Fail-open to not break the game

    async def close(self):
        await self.client.aclose()
        logger.info("WikipediaValidator client closed.")


# Globalny instancja walidatora
validator = WikipediaValidator()
