# Państwa-Miasta — Agent Onboarding

Real-time multiplayer Państwa-Miasta po polsku, FastAPI + WebSocket + vanilla JS.
Solo project, prod target: smartphone-first; obecnie bez reklam w grze i bez kont użytkowników.

## Stack

- **Python 3.13**, package manager `uv`
- **Backend**: FastAPI, `aiosqlite` / libSQL (dev: lokalny `panstwa_miasta.db`; **prod: Turso**
  embedded replica przez `LIBSQL_URL` + `LIBSQL_AUTH_TOKEN`), WebSocket per room
- **Frontend**: vanilla JS / HTML / CSS, no framework, no jQuery. ES modules in `static/js/`
- **Tests**: `pytest` (Python, 35 tests) + `jest` (JS, 59 tests)
- **Lint/format/types**: `ruff` (lint + format), `ty` (type check)
- **Quality gate**: SonarQube Cloud (projekt `filip-org_panstwa-masta`; CI: `SONAR_TOKEN` w GitHub Secrets). W SonarCloud ustaw **main branch** na `main` (nie `master`), inaczej darmowy plan nie zmapuje analizy na gałąź `main` z GitHuba.

## WSL setup (one-time)

This workspace lives on WSL but the host PATH may resolve `npm` / `npx`
to the Windows-side binaries under `/mnt/c/Program Files/nodejs/`. They
choke on Linux-style paths (`ERR_INVALID_URL`). Always use a Linux-side
Node installed via nvm:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh"
nvm install --lts          # currently Node 24
```

After install: `which npx` should point at
`/home/filip/.nvm/versions/node/v<x>/bin/npx`. The MCP memory server in
`.cursor/mcp.json` references that absolute path explicitly — if you
upgrade Node via `nvm install`, update that path too.

## Daily QA loop (run before every commit)

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run pytest -q --cov=src/panstwa_miasta --cov-report=xml

# JS tests must go through Docker on WSL — local `npm test` hits a
# Windows-path issue with WSL workspaces. Use:
docker run --rm -v "$PWD:/work" -w /work node:20-alpine \
  sh -c "npm ci --silent && npm test -- --coverage \
         --coverageReporters=lcov --coverageDirectory=coverage-js"
```

## Branch & PR workflow

- Branches: `feat/...`, `fix/...`, `chore/...`, `refactor/...`, `docs/...`
- Never push to `main` directly. Open PR, enable auto-merge with squash:
  `gh pr merge <n> --auto --squash`
- CI is required: backend (ruff/ty/pytest) + frontend (jest). Dependabot
  PRs are rebased onto `main` when they fall behind.
- Commit cadence: 100–200 changed lines max per commit (see
  `.cursor/rules/commit-cadence.mdc`).

## Data architecture (important)

Static game data lives in **SQLite tables**, not files:

- `countries` table — seeded from `src/panstwa_miasta/countries_seed.py`
  (205 countries: 194 UN-recognized + 11 limited recognition, with
  continent, capital, population, etc.)
- `names` table — seeded from `src/panstwa_miasta/names_seed.py`
  (1455 Polish first names, M/F, with occurrence count from PESEL register)
- `jobs` table — seeded from `src/panstwa_miasta/jobs_seed.py` (~1450
  zawodów + opcjonalny `kod` PKD). Cache ``JOBS`` w ``data.py`` wypełnia
  ``reload_jobs()`` (pełna fraza + alias pierwszego słowa). Regeneracja
  seeda: ``uv run python scripts/build_jobs_seed.py --zawody PLIK --liniowy PLIK``.
- `cities` table — `id`, `nazwa`, `nazwa_norm`, `kraj` (jak w ``countries.name``),
  `kraj_norm`. Seed: Wikidata PL + ``scripts/seed_data/cities_geonames.jsonl.gz``.
  Walidacja **Miasto** z cache ``MIASTA`` (`reload_miasta()`), bez Wikidata w runtime.
- `animal_norms` / `plant_norms` — seed z ``scripts/seed_data/*.jsonl.gz``
  (eksport: ``scripts/export_norms_seed_data.py``; skrapery wiki/GBIF w ``scripts/``).
  Cache ``ZWIERZETA`` / ``ROSLINY`` przez ``reload_zwierzeta()`` / ``reload_rosliny()`` —
  **bez** odpytywania API w runtime.

In-memory caches `COUNTRIES`, `MIASTA`, `NAMES`, `JOBS`, `ZWIERZETA`, `ROSLINY`
are populated by `reload_*` in the FastAPI lifespan handler (and pytest
fixtures via `tests/conftest.py`).

Normalization is `manager.normalize_text` / `db._name_norm`: lowercase,
strip, collapse whitespace. Both DB and validation must use it.

## Letter randomization

`Room._refill_letter_queue()` in `manager.py` splits the alphabet into
`fresh` (not in `_recent_letters` deque, capacity 7) and `stale`. Both
shuffled independently, `stale` pushed to the bottom of the queue. This
prevents letters from repeating in consecutive games. `restart_game`
continues the existing queue — does **not** reshuffle.

## Sonar gotchas (false-positive list)

- `secrets.SystemRandom().shuffle()` in `manager.py` is **CSPRNG**, not
  weak random. Rule `python:S2245` fires regardless of source. Mark
  hotspots as Safe; **do not** replace with `random.shuffle`.
- Google Fonts `<link>` without `integrity` (rule Web:S5725) — Google
  does not publish SRI hashes. Mark as Safe.
- `*_seed.py` modules are excluded from analysis via
  `sonar.exclusions` — they are data, not code.

## Open work

- **Jobs**: nazwy są curatowane w ``jobs_seed.py`` (nie surowe PKD w grze).

**Kolejka po sprincie (P3):** integracja WS (pytest, 2 klientów) i więcej gałęzi reconnect w Jest; podbijanie `VERSION` w `static/sw.js` przy release JS; kuracja seedów według feedbacku z gry; snapshot rundy / Redis tylko przy multi-worker lub twardym wymogu wznowienia po restarcie procesu; `load_from_db` → logger zamiast `print`.

**Wzrost / monetyzacja (backlog):** reklamy poza aktywną rundą + CMP i aktualizacja polityki/cookies; konta użytkowników (ranking, RODO) przy zachowaniu lobby anonimowego; strona `/wspolprace` lub sekcja partnerska; zdarzenia Umami (np. klik „Wesprzyj serwer” przez `data-umami-event`); pełne CSP z whitelistą zewnętrznych skryptów.

**Produkcja / bezpieczeństwo:** nowe pokoje dostają **serwerowe** ID (10 znaków alfanumerycznych) przez `POST /api/rooms`; odwołania po grze wymagają tokenu z WS `appeal_token`; healthcheck `GET /healthz`; nagłówki w `deploy/Caddyfile.example`; smoke w `deploy/prod-smoke-check.sh` i opcjonalny HTTPS w `deploy/vps-pull-and-restart.sh` (`PROD_BASE_URL`).

Zrobione: **Faza 3** (overlay 3–2–1 przed loterią litery, `playCountdownHaptic`,
`prefers-reduced-motion`), **Faza 4** (panel udostępniania po `game_over`,
`room_id` w `round_results`, `/share/{id}`), **Sprint monetyzacji** (BuyCoffee w stopce,
Umami Cloud przez env, `robots.txt` / `sitemap.xml`, OG/canonical na landingu).

## Persistent memory (this file + Cursor rules)

- This `AGENTS.md` is read automatically at the start of every new chat
- More focused rules live in `.cursor/rules/*.mdc`
- Dynamic facts (decisions, gotchas discovered mid-work) are stored in
  a knowledge graph via MCP memory server — see `.cursor/mcp.json`
