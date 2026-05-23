# Państwa-Miasta

[![CI](https://github.com/filki/panstwa-miasta/actions/workflows/ci.yml/badge.svg)](https://github.com/filki/panstwa-miasta/actions/workflows/ci.yml)
[![SonarCloud](https://sonarcloud.io/api/project_badges/measure?project=filip-org_panstwa-masta&metric=alert_status)](https://sonarcloud.io/dashboard?id=filip-org_panstwa-masta)

Klasyczna gra Państwa-Miasta w czasie rzeczywistym. Bez kont, bez reklam.
Odpowiedzi sprawdzane względem lokalnych list na serwerze.

> Stwórz pokój, wyślij kod znajomym, grajcie razem.

## Stack

- **Backend**: Python 3.13 / FastAPI + WebSockets
- **Frontend**: vanilla JS / HTML / CSS, PWA, mobile-first
- **Baza**: SQLite (dev) / Turso embedded replica (prod) przez libSQL
- **Walidacja**: dane w SQLite + cache w pamięci — bez zewnętrznego API przy punktacji
- **Package manager**: [uv](https://docs.astral.sh/uv/)
- **Jakość**: `ruff` (lint+format), `ty` (type check), SonarCloud, pytest + Jest

## Quickstart (dev)

```bash
# Zależności
uv sync --extra dev --extra redis
npm ci

# Uruchom (z Turso — .env wymagane) lub bez (lokalny SQLite)
uv run uvicorn src.panstwa_miasta.main:app --reload --port 8000
```

Aplikacja pod `http://localhost:8000`.

### Docker

```bash
docker compose up -d
```

## Testy

```bash
uv run pytest                 # Python (183 testów, ~87% coverage)
npm test                      # Frontend Jest (121 testów)
```

## Jakość kodu

| Krok | Komenda |
|------|---------|
| Format | `uv run ruff format --check .` |
| Lint | `uv run ruff check .` |
| Typy | `uv run ty check` |
| Coverage target | 80% (SonarCloud) |

## Środowiska

- **Dev**: lokalny SQLite (plika `panstwa_miasta.db`)
- **Prod**: Turso embedded replica (Hetzner + Caddy reverse proxy)
- **CI**: GitHub Actions (ruff → ty → pytest → jest → SonarCloud)

## Struktura

```
src/panstwa_miasta/   # backend
static/               # frontend (HTML, CSS, JS, service worker)
tests/                # pytest + Jest
deploy/               # Caddyfile, systemd, runbooki
scripts/              # build, seed, narzędzia developerskie
knowledge_base/       # lokalna baza wiedzy (Kùzu) dla agenta
.zed/                 # konfiguracja Zeda (MCP, profile)
```

## Workflow

Trunk-based: `main` zawsze deployowalna. Zmiany przez `feat/*` / `fix/*` / `chore/*` → PR z auto-merge squash. CI wymagane.
