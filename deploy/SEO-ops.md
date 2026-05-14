# SEO i operacje (backlog)

Nie blokuje wdrożenia kolejki RAG. Wykonuj jako małe PR lub zadania operatorskie.

## Search Console

- Zweryfikuj właściwość dla `https://panstwamiasta.com.pl` (apex).
- Prześlij mapę: `https://panstwamiasta.com.pl/sitemap.xml` (generowana w aplikacji).
- Monitoruj indeksację stron prawnych (`/polityka-prywatnosci`, `/regulamin`, `/cookies`).

## www → apex

- Upewnij się, że Caddy przekierowuje `www` na apex (lub odwrotnie — jeden kanoniczny host).
- Canonical w [`static/index.html`](../static/index.html) wskazuje apex.

## Robots i pokoje

- [`/robots.txt`](../src/panstwa_miasta/main.py) — Allow `/`, Disallow `/room/`.
- Strony pokoju: `noindex` w szablonie pokoju (jeśli jeszcze brak — osobny PR).

## Monitoring

- Uptime na `/` i `/healthz` (patrz [`deploy/README.md`](README.md) § Uptime Kuma).
- Po włączeniu RAG: alert na 503 `/api/words/report` w godzinach szczytu.

## Opcjonalnie

- Umami (`UMAMI_*` w `env.example`).
- Strona `/wspolprace` — osobny PR treści.
