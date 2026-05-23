# n8n na VPS (automatyzacja kolejki słów)

> **Produkcja (2026-05):** stack n8n **nie jest** uruchomiony na VPS gry.
> Pliki w repo służą do przyszłego stagingu RAG (`PM_RAG_QUEUE_ENABLED`).

Osobny stack Docker obok gry — restart n8n nie wymaga restartu `panstwa-miasta`.

## Start

```bash
cd deploy/n8n
cp .env.example .env   # uzupełnij host i N8N_ENCRYPTION_KEY
docker compose up -d
curl -sI http://127.0.0.1:5678/healthz
```

## Caddy (subdomena)

Wystaw `https://n8n.twoja-domena.pl` na `127.0.0.1:5678` (reverse proxy). `WEBHOOK_URL` w `.env` musi wskazywać publiczny HTTPS z końcowym `/`.

## MCP (opcjonalnie, autorstwo workflow)

W UI: **Settings → Instance-level MCP** (wymaga n8n 2.2+). Służy do budowy workflow z klienta MCP (np. Cursor), nie do ruchu graczy w produkcji.

## Sekrety

- Token Hugging Face Inference — credential w n8n, nie w repo.
- `PM_WORDS_WORKER_TOKEN` — w `EnvironmentFile` aplikacji gry; ten sam token w nagłówku HTTP workflow.

## Backup

Wolumen `n8n_data` (`docker volume inspect deploy-n8n_n8n_data`). Przed aktualizacją obrazu: `docker compose down` + kopia wolumenu.

## Workflow

Import: `workflows/word-queue-bielik.json` (harmonogram → pending → HF → decyzja).
