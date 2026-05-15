#!/usr/bin/env bash
# Faza C: smoke na stagingu z LIBSQL_* (po merge PR z skip-seed + deploy poll).
set -euo pipefail

APP_DIR="${DEPLOY_APP_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$APP_DIR"

if [[ -z "${LIBSQL_URL:-}" ]] || [[ -z "${LIBSQL_AUTH_TOKEN:-}" ]]; then
  echo "Ustaw LIBSQL_URL i LIBSQL_AUTH_TOKEN (np. source /etc/panstwa-miasta.env)." >&2
  exit 1
fi

export PATH="${HOME}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin}"

echo "=== Usuń starą replikę przed pierwszym testem ==="
rm -f panstwa_miasta.db panstwa_miasta.db-info panstwa_miasta.db-wal panstwa_miasta.db-shm

echo "=== Start uvicorn (foreground — Ctrl+C po smoke) lub użyj systemd ==="
echo "Przykład: uv run uvicorn panstwa_miasta.main:app --host 127.0.0.1 --port 8000"
echo ""
echo "W drugim terminalu:"
echo "  ./deploy/turso-poll-healthz.sh 1200"
echo "  uv run python scripts/db_table_counts.py"
echo "  ./deploy/prod-smoke-check.sh   # PROD_BASE_URL=http://127.0.0.1:8000 jeśli lokalnie"
echo ""
echo "Rollback ćwiczeniowy: wyłącz LIBSQL_*, przywróć panstwa_miasta.db z kopii, restart."
