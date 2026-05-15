#!/usr/bin/env bash
# Faza 0 planu Turso: backup + baseline COUNT(*) na VPS (SQLite, bez LIBSQL_*).
# Import do chmury: na laptopie z Turso CLI — patrz deploy/TURSO-cutover.md Faza 1.
set -euo pipefail

APP_DIR="${DEPLOY_APP_DIR:-/srv/panstwa-miasta}"
cd "$APP_DIR"

if [[ -n "${LIBSQL_URL:-}" ]] || [[ -n "${LIBSQL_AUTH_TOKEN:-}" ]]; then
  echo "Ostrzeżenie: LIBSQL_* ustawione — baseline powinien być z czystego SQLite (wyłącz env)." >&2
fi

export PATH="${HOME}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

echo "=== Backup ==="
DEPLOY_APP_DIR="$APP_DIR" ./deploy/backup-db.sh

STAMP="$(date -u +%Y%m%d)"
PRE_COPY="${APP_DIR}/panstwa_miasta.db.pre-turso-${STAMP}"
if [[ -f "${APP_DIR}/panstwa_miasta.db" ]]; then
  cp -a "${APP_DIR}/panstwa_miasta.db" "$PRE_COPY"
  echo "Kopia: $PRE_COPY"
fi

echo "=== Baseline counts (counts-pre-${STAMP}.json) ==="
uv run python scripts/db_table_counts.py > "${APP_DIR}/counts-pre-${STAMP}.json"
cat "${APP_DIR}/counts-pre-${STAMP}.json"

echo ""
echo "Następny krok (na maszynie z Turso CLI, poza prod):"
echo "  scp user@vps:${PRE_COPY} ."
echo "  turso db import <nazwa-bazy> panstwa_miasta.db.pre-turso-${STAMP}"
echo "  turso db shell <nazwa-bazy> \"SELECT COUNT(*) FROM cities;\""
echo "Porównaj COUNT z counts-pre-${STAMP}.json"
