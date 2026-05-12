# Państwa-Miasta

[![CI](https://github.com/filki/panstwa-miasta/actions/workflows/ci.yml/badge.svg)](https://github.com/filki/panstwa-miasta/actions/workflows/ci.yml)

Klasyczna gra Państwa-Miasta odpalana w kilka sekund na telefonie. Bez kont; odpowiedzi sprawdzane względem **lokalnych** list na serwerze (m.in. miasta, zwierzęta, rośliny).

> Stwórz pokój, wyślij kod znajomym, grajcie razem w czasie rzeczywistym.

## Stack

- **Backend**: FastAPI + WebSockets, `aiosqlite`
- **Frontend**: Pure HTML/CSS/JS, PWA (manifest + service worker), mobile-first
- **Walidacja**: zbiory w SQLite / cache w pamięci (build offline dla części danych) — bez zewnętrznego API w locie przy punktacji
- **Package manager**: [uv](https://docs.astral.sh/uv/)

## Quickstart (dev)

```bash
uv sync --extra dev
uv run uvicorn panstwa_miasta.main:app --reload
```

Aplikacja działa pod `http://localhost:8000`.

### Docker (serwer cały czas w tle)

Żeby nie odpalać `uvicorn` po każdym restarcie IDE:

```bash
docker compose up -d
```

- Adres jak wyżej: `http://localhost:8000` (port zbindowany tylko na loopback).
- **`--reload`**: zmiany w `src/` i `static/` na hoście widać po zapisie pliku.
- Baza `panstwa_miasta.db` leży w katalogu projektu na hoście (montowanie `.:/app`).
- Zatrzymanie: `docker compose down`.

Po zmianie zależności w `pyproject.toml` / `uv.lock`: `docker compose build --no-cache` i znowu `up`.

#### Docker + ngrok (tunel w drugim kontenerze)

Serwis **`ngrok`** jest na profilu Compose **`tunnel`** — domyślne `docker compose up -d` uruchamia **tylko `web`** (bez błędów auth przy pustym tokenie). Tunel włączasz tak:

1. **Token** z [ngrok — Your Authtoken](https://dashboard.ngrok.com/get-started/your-authtoken) (konto **zweryfikowane** e‑mailem — inaczej `ERR_NGROK_4018`).
2. W katalogu z `docker-compose.yml` plik **`.env`** (skopiuj z `.env.example`), np.:
   - **Sposób A:** `COMPOSE_PROFILES=tunnel` oraz `NGROK_AUTHTOKEN=...` → potem `docker compose up -d` (Docker Desktop też wczyta `.env`).
   - **Sposób B:** sam `NGROK_AUTHTOKEN=...` w `.env`, a tunel tylko gdy uruchomisz:  
     `docker compose --profile tunnel up -d`

Publiczny URL: `docker compose logs ngrok` albo panel inspect: **`http://127.0.0.1:14040`** (zmiana portu: `NGROK_INSPECT_PORT` w `.env`). Konflikt z lokalnym ngrok na **4040** na hoście — dlatego domyślnie **14040**.

#### Windows: skrypt z tunelem

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned   # jednorazowo, jeśli skrypty są zablokowane
.\scripts\dev-docker-ngrok.ps1
```

To `docker compose --profile tunnel up -d --build` + przypomnienie adresów. Bez `NGROK_AUTHTOKEN` w `.env` kontener ngrok zakończy się błędem — `web` nadal działa pod `http://127.0.0.1:8000`.

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
