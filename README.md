# Państwa-Miasta

[![CI](https://github.com/filki/panstwa-miasta/actions/workflows/ci.yml/badge.svg)](https://github.com/filki/panstwa-miasta/actions/workflows/ci.yml)

Klasyczna gra Państwa-Miasta odpalana w pięć sekund na telefonie. Bez kont, bez reklam, z Wikipedią jako sędzią.

> Stwórz pokój, wyślij kod znajomym, grajcie razem w czasie rzeczywistym.

## Stack

- **Backend**: FastAPI + WebSockets, `aiosqlite`, `httpx` (Wikidata)
- **Frontend**: Pure HTML/CSS/JS, PWA (manifest + service worker), mobile-first
- **Walidacja**: Wikidata API — koniec sporów typu „Audi to miasto?"
- **Package manager**: [uv](https://docs.astral.sh/uv/)

## Quickstart (dev)

```bash
uv sync --extra dev
uv run uvicorn panstwa_miasta.main:app --reload
```

Aplikacja działa pod `http://localhost:8000`.

## Quality gates

Wszystko leci w CI na każdy push i PR do `main`:

| Krok | Komenda lokalna |
| --- | --- |
| Format | `uv run ruff format --check .` |
| Lint | `uv run ruff check .` |
| Typy | `uv run ty check src` |
| Testy (Python) | `uv run pytest` |
| Testy (JS) | `npm test` |

Auto-fix lokalnie: `uv run ruff format . && uv run ruff check --fix .`.

## Struktura

```
src/panstwa_miasta/   # backend (FastAPI app)
static/               # frontend (index.html, room.html, css, js, sw)
tests/                # pytest (~87% coverage)
.github/workflows/    # CI
```

## Workflow

Trunk-based — `main` to jedyna stała gałąź, zawsze deployowalna. Każda zmiana idzie krótką gałęzią `feat/*` / `fix/*` / `chore/*` przez PR. Branch protection wymusza zielone CI przed mergem.

Commit cadence: 100–200 zmienionych linii na commit (`.cursor/rules/commit-cadence.mdc`).
