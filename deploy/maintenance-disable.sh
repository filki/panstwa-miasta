#!/usr/bin/env bash
# Wyłącza ręczny tryb konserwacji (automatyczny przy 502 zostaje w Caddyfile).
set -euo pipefail

MAINT_FLAG="${PM_MAINTENANCE_FLAG:-/etc/caddy/maintenance.on}"

sudo rm -f "$MAINT_FLAG"
sudo systemctl reload caddy
echo "Ręczny tryb konserwacji wyłączony."
