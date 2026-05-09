import httpx
import asyncio
from typing import Dict, Set

class WikipediaValidator:
    def __init__(self):
        self.cache: Dict[str, bool] = {}
        self.client = httpx.AsyncClient(timeout=5.0)
        
    async def validate(self, term: str, category: str) -> bool:
        """
        Sprawdza czy dany termin istnieje w polskiej Wikipedii.
        Opcjonalnie można sprawdzać kategorie, ale na razie sprawdzamy samą egzystencję strony.
        """
        term = term.strip().lower()
        if not term:
            return False
            
        cache_key = f"{category}:{term}"
        if cache_key in self.cache:
            return self.cache[cache_key]
            
        try:
            params = {
                "action": "wbsearchentities",
                "search": term,
                "language": "pl",
                "format": "json"
            }
            # Używamy API Wikidata - jest dużo bardziej restrykcyjne i precyzyjne (opisy to np. "miasto w Polsce", "gatunek ssaka")
            response = await self.client.get("https://www.wikidata.org/w/api.php", params=params)
            data = response.json()
            
            search_results = data.get("search", [])
            if search_results:
                # Bierzemy pierwszy (najbardziej trafny) wynik
                first_result = search_results[0]
                title = first_result.get("label", "").lower()
                description = first_result.get("description", "").lower()
                
                # Słowa kluczowe dla kategorii
                keywords = {
                    "Miasto": ["miasto", "miejscowość", "stolica", "wieś", "osada", "gmina", "aglomeracja", "prowincja"],
                    "Zwierzę": ["zwierzę", "gatunek", "rodzina", "rząd", "ptak", "ryba", "ssak", "gad", "płaz", "owad", "pająk", "stawonóg"],
                    "Roślina": ["roślina", "gatunek", "drzewo", "krzew", "kwiat", "bylina", "zioło", "owoc", "warzywo", "grzyb", "roślin"]
                }
                
                # Jeśli tytuł się zgadza (lub jest bardzo blisko)
                if term in title or title in term:
                    if category in keywords:
                        # Wyszukujemy słów kluczowych w precyzyjnym opisie Wikidata
                        if any(kw in description for kw in keywords[category]):
                            self.cache[cache_key] = True
                            return True
                    else:
                        self.cache[cache_key] = True
                        return True
            
            self.cache[cache_key] = False
            return False
        except Exception as e:
            print(f"⚠️ Błąd walidacji Wikipedia dla {term}: {e}")
            # W razie błędu sieci, domyślnie uznajemy (żeby nie psuć gry)
            return True

    async def close(self):
        await self.client.aclose()

# Globalny instancja walidatora
validator = WikipediaValidator()
