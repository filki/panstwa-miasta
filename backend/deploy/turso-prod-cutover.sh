#!/usr/bin/env bash
# Faza 4: cutover produkcji na Turso (embedded replica). Wymaga wcześniejszego importu do Turso.
# Uruchom jako root lub użytkownik z sudo do systemctl. LIBSQL_* muszą być w /etc/panstwa-miasta.env.
set -euo pipefail

APP_DIR="${DEPLOY_APP_DIR:-/srv/panstwa-miasta}"
ENV_FILE="${PM_ENV_FILE:-/etc/panstwa-miasta.env}"

if [[ ! -f "$ENV_FILE" ]] || ! grep -qE '^LIBSQL_URL=' "$ENV_FILE"; then
  echo "Brak LIBSQL_URL w ${ENV_FILE} — ustaw Turso przed cutoverem." >&2
  exit 1
fi

echo "=== Stop aplikacji ==="
if [[ "$(id -u)" -eq 0 ]]; then
  systemctl stop panstwa-miasta
else
  sudo -n systemctl stop panstwa-miasta
fi

cd "$APP_DIR"
echo "=== Usuwanie lokalnej repliki / sidecarów ==="
rm -f panstwa_miasta.db panstwa_miasta.db-info panstwa_miasta.db-wal panstwa_miasta.db-shm

echo "=== Start aplikacji ==="
if [[ "$(id -u)" -eq 0 ]]; then
  systemctl start panstwa-miasta
else
  sudo -n systemctl start panstwa-miasta
fi

echo "=== Poll /healthz (do 20 min) ==="
chmod +x "${APP_DIR}/deploy/turso-poll-healthz.sh"
"${APP_DIR}/deploy/turso-poll-healthz.sh" 1200 10

echo "=== Counts po starcie ==="
# shellcheck source=/dev/null
set -a && source "$ENV_FILE" && set +a
uv run python scripts/db_table_counts.py

echo "=== Smoke ==="
PROD_BASE_URL="${PROD_BASE_URL:-https://panstwamiasta.com.pl}" "${APP_DIR}/deploy/prod-smoke-check.sh"

echo "Cutover zakończony. Porównaj counts z counts-pre-*.json i przetestuj grę ręcznie."
