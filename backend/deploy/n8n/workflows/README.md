# Import workflow kolejki słów

1. W n8n: **Workflows → Import from file** — `word-queue-bielik.json`.
2. Ustaw zmienne środowiskowe kontenera n8n: `PM_APP_BASE_URL=https://panstwamiasta.com.pl` (bez końcowego `/`).
3. Credential **HTTP Header Auth** (`Authorization: Bearer <PM_WORDS_WORKER_TOKEN>`) — ten sam token co w `EnvironmentFile` gry.
4. Credential **Hugging Face API** — token z konta z zaakceptowanymi warunkami modelu Bielik.
5. Po imporcie podłącz credentials do węzłów HTTP i HF; usuń `REPLACE_ME` z eksportu.
6. Test ręczny na stagingu z jednym wierszem `pending`; dopiero potem aktywuj harmonogram.

Zaakceptowane zgłoszenia **nie** dopisują automatycznie wpisów do seedów — kuracja pozostaje ręczna (`scripts/review_suggestions.py`).
