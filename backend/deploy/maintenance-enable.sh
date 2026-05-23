#!/usr/bin/env bash
# Włącza tryb konserwacji (strona z deploy/maintenance/) — bez restartu aplikacji.
# Wymaga zaktualizowanego Caddyfile z deploy/Caddyfile.example (handle_errors + @maintenance).
set -euo pipefail

APP_DIR="${DEPLOY_APP_DIR:-/srv/panstwa-miasta}"
MAINT_FLAG="${PM_MAINTENANCE_FLAG:-/etc/caddy/maintenance.on}"

if [[ ! -f "${APP_DIR}/backend/deploy/maintenance/index.html" ]]; then
  echo "Brak ${APP_DIR}/backend/deploy/maintenance/index.html — zrób git pull w APP_DIR." >&2
  exit 1
fi

sudo touch "$MAINT_FLAG"
sudo systemctl reload caddy
echo "Tryb konserwacji włączony ($MAINT_FLAG). Wyłącz: deploy/maintenance-disable.sh"
