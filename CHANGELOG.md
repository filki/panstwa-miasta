# Changelog

Wersje produktu dla agentów i ludzi. Format inspirowany [Keep a Changelog](https://keepachangelog.com/pl/1.1.0/).

**Numeracja:** semver w tym pliku opisuje **kamienie milowe produktu**, nie `version` w `pyproject.toml` (tam nadal `0.1.0`). **Service worker** ma własną linię `pm-vN` w `static/sw.js` — podbijaj przy zmianach JS/CSS, które muszą przebić cache PWA.

**Źródła prawdy:** `git log`, squash-merge PR na `main`, `AGENTS.md`, runbooki w `deploy/`, graf MCP memory.

---

## [Unreleased]

### Proces / intencja

Backlog po sprintach — bez obietnic dat. Priorytety z `AGENTS.md`: stabilność gry i deployu przed monetyzacją i pełnym RAG.

### Planowane

- Testy integracyjne WebSocket (pytest, ≥2 klientów) i więcej gałęzi reconnect w Jest.
- Kuracja seedów (`jobs`, `things`, fauna/flora) według feedbacku z gry.
- Snapshot rundy / Redis dopiero przy multi-worker lub twardym wymogu wznowienia po restarcie procesu.
- `load_from_db` → logger zamiast `print`.
- Monetyzacja: reklamy poza rundą + CMP; konta (ranking, RODO) przy zachowaniu anonimowego lobby.
- `/wspolprace` — dopiero przy realnych partnerstwach (świadomie pominięte w SEO 0.12.x).
- Pełne CSP w Caddy; zdarzenia Umami (np. `data-umami-event` na „Wesprzyj serwer”).

---

## [0.12.1] — 2026-05-14

### Proces / intencja

Sprint SEO dodał statyczny blok „Jak grać?” pod listą pokoi; użytkownik zobaczył **dwa razy to samo** obok karuzeli. Decyzja: **jedna warstwa treści w UI**; SEO zostaje w meta, JSON-LD, sitemap i stronach prawnych — bez duplikatu wizualnego.

### Zmiany

- Usunięty dolny blok `.landing-seo` z landingu (PR #82).

---

## [0.12.0] — 2026-05-14

### Proces / intencja

Domknięcie **technicznego SEO** bez strony partnerskiej. Search Console i DNS/www to kroki operatorskie (`deploy/SEO-ops.md`), nie kod.

### Zmiany

- Open Graph na stronach prawnych; `og:locale` na landingu.
- Opcjonalna meta `google-site-verification` z env `GOOGLE_SITE_VERIFICATION`.
- Krótki eksperyment ze statycznym opisem gry na landingu — wycofany w 0.12.1 (PR #81, #82).

### Ograniczenia

- `/wspolprace` celowo **nie** w sitemap.
- Indeksacja w GSC wymaga ręcznej konfiguracji na VPS.

---

## [0.11.0] — 2026-05-14

### Proces / intencja

Gracze zgłaszają słowa spoza słownika; **pełny RAG na produkcji wyłączony** (`PM_RAG_QUEUE_ENABLED`). Kolejka ma być **ręczna**: zapis do DB, właściciel przegląda i dopisuje do seedów. Turso **tylko** dla inboxu słownika (`PM_DICTIONARY_LIBSQL_*`), gra zostaje na lokalnym SQLite — bez powtórki pełnego cutoveru z 0.9.0.

### Zmiany

- `POST /api/dictionary/suggestions` — zawsze zapis `pending` w `dictionary_suggestions`.
- `/api/words/report` bez RAG przekierowany na ten sam zapis (komunikat: AI wyłączone, weryfikacja człowieka).
- `scripts/review_suggestions.py` — lista/ocena propozycji.
- Fallback ścieżki SQLite, gdy `panstwa_miasta.db` w repo jest tylko do odczytu (dev WSL).
- Akceptowane odpowiedzi **Rzecz** → tabela `things` (osobno od kolejki zgłoszeń).

### Ograniczenia

- Brak auto-merge do seedów po kliknięciu „Zapisz do słownika”.
- Worker AI i n8n gotowe w kodzie, ale **feature-flag** na prod.

---

## [0.10.0] — 2026-05-14

### Proces / intencja

Incydenty: rozłączenie w rundzie (timer 0, STOP), lobby **9/8** graczy, za krótkie podsumowanie rundy. Priorytet: **spójny stan WS** i roster tylko z aktywnych socketów, nie z „duchów” w SQLite.

### Zmiany

- Resume rundy po reconnect: timery, faza STOP, overlay wyników z `veto_ends_at`.
- `connected_players` w `score_update`; lobby renderowane tylko w fazie lobby.
- `RESULTS_PHASE_SECONDS = 30`; limit nicku 16 znaków.
- Klient: natychmiastowy submit przy `stop_seconds_left <= 0`; ignorowanie starych `onclose` (`pmWsGeneration`).

### Ograniczenia

- Pojedynczy worker — brak Redis między procesami.
- Stare pokoje z rozjazdem DB vs socket wymagają ręcznego sprzątania na VPS.

---

## [0.9.0] — 2026-05-14

### Proces / intencja

Dwa równoległe tory: **Turso** jako primary oraz **RAG** na `dictionary_suggestions`. Hipoteza: embedded replica na VPS + sync do chmury.

### Zmiany

- `db_backend.connect()` — libSQL embedded replica przy `LIBSQL_*`.
- Kolejka słów: API `/api/words/*`, worker, szkielet n8n (`deploy/n8n/`).
- Runbook `deploy/TURSO-cutover.md`.

### Ograniczenia / wnioski

- Cutover Turso na prod → **502**; rollback do czystego SQLite.
- RAG na prod domyślnie **off**.
- Pełny Turso odrzucony na rzecz hybrydy słownika (0.11.0).

---

## [0.8.0] — 2026-05-14

### Proces / intencja

Przygotowanie pod **wzrost organiczny** i lekki dochód bez reklam w rundzie: widoczność w Google + dobrowolne wsparcie, bez kont użytkowników.

### Zmiany

- `robots.txt`, `sitemap.xml`, canonical i OG na landingu, `noindex` na `/room/*` i `/share/*`.
- Stopka: BuyCoffee; hook Umami przez env.
- Landing: CTA wsparcia, iteracje SEO sprint 2 (karuzela „Jak grać?” jako jedyna warstwa instrukcji w UI po 0.12.1).

---

## [0.7.0] — 2026-05-14

### Proces / intencja

Produkcja na Hetznerze — twardzenie przed ruchem: zgadywalne ID pokoi i odwołania bez sesji to realne ryzyka.

### Zmiany

- `POST /api/rooms` — serwerowe ID pokoi (~10 znaków).
- Tokeny odwołań (`appeal_token` + `Authorization` na `/api/rooms/{id}/appeals`).
- `GET /healthz`; nagłówki w `deploy/Caddyfile.example`.
- Smoke: `deploy/prod-smoke-check.sh`, opcjonalny HTTPS w deploy po `PROD_BASE_URL`.

---

## [0.6.0] — 2026-05-13

### Proces / intencja

Gra ma **domykać rundę społecznie** (veto na Rzecz) i **udostępniać wynik** bez konta. Lobby publiczne musi się nie zapychać „martwymi” pokojami.

### Zmiany

- Veto na kategorii Rzecz; pełnoekranowe podsumowanie rundy; overlay 3–2–1 przed loterią litery.
- `game_over`: wyniki, historia rund, `/share/{id}` z OG (strona `noindex`).
- Max 8 graczy, quick join, rozwiązywanie idle lobby (5 min), appeals po grze.
- Avatary PNG + `avatar.js`.

---

## [0.5.0] — 2026-05-13

### Proces / intencja

Smartphone-first i **konkurencja z Gartic Phone**: landing i lobby jako pierwsze wrażenie, nie tylko „formularz w HTML”.

### Zmiany

- Landing w stylu Gartic: bento/glass, karuzela „Jak grać?”, aktywne pokoje (tabela desktop / karty mobile).
- Lobby z gotowością, zaproszeniem, rosterem; rundy 10/22, limit 120 s.
- Pseudonim na starcie, losowy nick, szybka gra z landingu.

---

## [0.4.0] — 2026-05-12

### Proces / intencja

Solo dev — **CI + deploy** muszą być powtarzalne; reconnect i limity to warunek gry wieloosobowej na jednym procesie.

### Zmiany

- GitHub Actions: ruff, ty, pytest, Jest; deploy na VPS (`deploy/vps-pull-and-restart.sh`).
- Limity HTTP/WS, Pydantic na wiadomościach WS, reconnect-safe disconnect.
- Skrypty ops: backup DB, smoke, `DEPLOY_ENABLED` w Variables.

---

## [0.3.0] — 2026-05-11

### Proces / intencja

Walidacja **offline** i przewidywalna: mniej Wikidata w runtime, więcej seedów w SQLite. Dane statyczne = tabele + `reload_*` przy starcie, nie pliki w runtime.

### Zmiany

- Miasta, państwa, imiona, zawody, zwierzęta, rośliny w seedach / SQL.
- Kolejka liter bez powtórek w kolejnych grach w tym samym pokoju (`_recent_letters`).
- SonarCloud na `main`; wykluczenia seedów z analizy.

### Ograniczenia

- `jobs_seed.py` to kuracja, nie surowy PKD w UI.
- Normalizacja: `manager.normalize_text` / `db._name_norm` — musi być spójna w DB i walidacji.

---

## [0.2.0] — 2026-05-10

### Proces / intencja

Sesja gry nie może ginąć przy odświeżeniu; host i rozwiązanie pokoju to podstawowy model uprawnień.

### Zmiany

- Persystencja pokoi i wyników w SQLite; host, korona, kick, rozwiązanie pokoju.
- Podsumowanie rundy z punktami per kategoria; akordeon na mobile.
- Reconnect grace; defer przepisania hosta przy rozłączeniu.

---

## [0.1.0] — 2026-05-08

### Proces / intencja

MVP: **Państwa-Miasta online po polsku**, WebSocket na pokój, bez frameworka na froncie — szybka iteracja i niski koszt hostingu.

### Zmiany

- Lobby, czat, losowanie litery, kategorie, STOP, liczenie punktów.
- FastAPI + vanilla JS; `uv` + pytest + Jest.
- Podział `static/` + `src/panstwa_miasta/`.

---

## Jak czytać ten plik (dla agentów)

1. Zacznij od **Unreleased** i `AGENTS.md` — nie zakładaj, że RAG lub pełny Turso są włączone na prod.
2. Przy bugach reconnect/lobby sprawdź **0.10.x** i `static/js/socket.js` + `handlers.py` (`score_update_payload`, resume).
3. Przy słowniku: **0.11.x**, `dictionary_suggestions`, env `PM_DICTIONARY_LIBSQL_*` vs lokalny SQLite.
4. Przy SEO: **0.8.x / 0.12.x**, `deploy/SEO-ops.md` — bez duplikowania „Jak grać?” w HTML.
5. Po zmianach JS/CSS podbij `VERSION` w `static/sw.js` i dopisz wpis w sekcji Unreleased przed release.
