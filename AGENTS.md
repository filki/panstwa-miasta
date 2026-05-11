# Państwa-Miasta — Agent Onboarding

Real-time multiplayer Państwa-Miasta po polsku, FastAPI + WebSocket + vanilla JS.
Solo project, prod target: smartphone-first, no ads, no accounts.

## Stack

- **Python 3.13**, package manager `uv`
- **Backend**: FastAPI, `aiosqlite` (single SQLite file `panstwa-miasta.db`), WebSocket per room
- **Frontend**: vanilla JS / HTML / CSS, no framework, no jQuery. ES modules in `static/js/`
- **Tests**: `pytest` (Python, 35 tests) + `jest` (JS, 59 tests)
- **Lint/format/types**: `ruff` (lint + format), `ty` (type check)
- **Quality gate**: SonarQube local (`localhost:9000`, project key `panstwa-masta`)

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
- `JOBS` — **still a Python set in `data.py`**. Don't touch it until the
  user explicitly asks. The user said: *"narazie nie dotykaj zawodów"*.

In-memory caches `COUNTRIES`, `NAMES` (sets of normalized strings) are
populated by `reload_countries()` / `reload_names()` in the FastAPI
lifespan handler (and pytest fixtures via `tests/conftest.py`).

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

- **Faza 3**: animacja losowania litery + countdown + wibracja mobilna
- **Faza 4**: `share_store.py` integration in game flow + endpointy
- **Eventual**: `JOBS` → SQL table (mirror countries/names pattern, but
  the user wants to redesign job names first — they come from PKD
  register and are awkward as game answers)

## Persistent memory (this file + Cursor rules)

- This `AGENTS.md` is read automatically at the start of every new chat
- More focused rules live in `.cursor/rules/*.mdc`
- Dynamic facts (decisions, gotchas discovered mid-work) are stored in
  a knowledge graph via MCP memory server — see `.cursor/mcp.json`
