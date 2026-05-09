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
                "action": "opensearch",
                "search": term,
                "limit": "1",
                "namespace": "0",
                "format": "json"
            }
            response = await self.client.get("https://pl.wikipedia.org/w/api.php", params=params)
            data = response.json()
            
            # data format: [query, [titles], [descriptions], [links]]
            if len(data) > 2 and data[1]:
                title = data[1][0].lower()
                description = data[2][0].lower() if data[2] else ""
                
                # Słowa kluczowe dla kategorii
                keywords = {
                    "Miasto": ["miasto", "miejscowość", "stolica", "wieś", "osada", "gmina", "aglomeracja", "prowincja"],
                    "Zwierzę": ["zwierzę", "gatunek", "rodzina", "rząd", "ptak", "ryba", "ssak", "gad", "płaz", "owad", "pająk", "stawonóg"],
                    "Roślina": ["roślina", "gatunek", "drzewo", "krzew", "kwiat", "bylina", "zioło", "owoc", "warzywo", "grzyb"] # grzyby często są w roślinie w tej grze ;)
                }
                
                # Jeśli tytuł się zgadza (lub jest bardzo blisko)
                if title == term or term in title:
                    # Jeśli mamy opis, sprawdzamy czy pasuje do kategorii
                    if category in keywords:
                        if any(kw in description for kw in keywords[category]):
                            self.cache[cache_key] = True
                            return True
                    else:
                        # Dla innych kategorii (jeśli byśmy dodali) akceptujemy samo istnienie
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
