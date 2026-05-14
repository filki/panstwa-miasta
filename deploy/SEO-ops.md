# SEO i operacje

## Zaimplementowane w aplikacji

- **Landing** (`static/index.html`): `description`, Open Graph, Twitter Card, `canonical` (apex),
  JSON-LD `WebApplication`.
- **`/robots.txt`** (`main.py`): `Allow: /`, `Disallow` dla `/api/`, `/ws/`, `/room/`, `/share/`,
  wpis `Sitemap`.
- **`/sitemap.xml`**: `/`, `/polityka-prywatnosci`, `/cookies`, `/regulamin` + `lastmod`.
- **Pokój** (`static/room.html`): `noindex`.
- **Udostępnianie wyniku** (`/share/{id}`): `noindex, nofollow` (OG zostaje pod podgląd linków).
- **Strony prawne**: `canonical` na apex w szablonach HTML.
- **Caddy** ([`Caddyfile.example`](Caddyfile.example)): stały redirect `www` → apex.

## Do zrobienia na serwerze / w panelach (operatorskie)

### Search Console

1. Właściwość typu **URL prefix**: `https://panstwamiasta.com.pl`.
2. Weryfikacja: rekord DNS TXT lub plik HTML (według kreatora Google).
3. **Mapa witryn:** `https://panstwamiasta.com.pl/sitemap.xml`.
4. Po deployu zmian SEO: „Sprawdź adres URL” dla `/` i stron prawnych; opcjonalnie „Poproś o
   indeksację” dla `/polityka-prywatnosci`, `/regulamin`, `/cookies`.
5. Monitoruj raport **Strony** / **Indeksowanie** — `/room/*` i `/share/*` nie powinny dominować
   (robots + noindex).

### www → apex

1. DNS: rekordy **A/AAAA** dla apex i dla `www` (oba na IP VPS) **albo** CNAME `www` → apex.
2. W `/etc/caddy/Caddyfile` blok `www.panstwamiasta.com.pl { redir https://panstwamiasta.com.pl{uri} permanent }`
   oraz osobny blok dla apex (jak w przykładzie).
3. Po zmianie: `sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy`.
4. Test: `curl -sI https://www.panstwamiasta.com.pl/` → `301` / `308`, `Location: https://panstwamiasta.com.pl/...`.

### Monitoring

- Uptime na `https://panstwamiasta.com.pl/` i `/healthz` (patrz [`README.md`](README.md) § Uptime Kuma).
- Po włączeniu RAG: alert na błędy `503` na `POST /api/words/report` w godzinach szczytu.

## Opcjonalnie (osobne PR / konfiguracja)

- **Umami:** `UMAMI_SCRIPT_URL` + `UMAMI_WEBSITE_ID` w unit systemd (`env.example`).
- **Strona `/wspolprace`** — treść marketingowa, osobny PR + wpis w sitemap.
- **Pełne CSP** w Caddy — osobny krok z whitelistą fontów i skryptów.
