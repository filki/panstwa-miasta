#!/usr/bin/env bash
# Rollback na VPS: checkout znanej rewizji + uv sync + restart (patrz deploy/README.md).
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Użycie: $0 <git-rev>   (np. abc1234 lub tag)" >&2
  exit 1
fi
rev="$1"

APP_DIR="${DEPLOY_APP_DIR:-/srv/panstwa-miasta}"
cd "$APP_DIR"

export PATH="${HOME}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

git fetch origin
git checkout main
git pull --ff-only origin main
git checkout "$rev"

cd "$APP_DIR/backend"
uv sync --frozen
cd "$APP_DIR"

if [[ "$(id -u)" -eq 0 ]]; then
  systemctl restart panstwa-miasta
else
  sudo -n systemctl restart panstwa-miasta
fi

code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)"
if [[ "$code" != "200" ]]; then
  echo "Smoke GET / zwrócił HTTP $code po rollbacku." >&2
  exit 1
fi

echo "Rollback OK: $(git rev-parse --short HEAD) (HTTP $code)"
