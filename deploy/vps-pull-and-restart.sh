#!/usr/bin/env bash
# Uruchamiany na VPS (np. z GitHub Actions przez SSH). Wymaga istniejącego klona
# repozytorium (deploy/README §1), gałęzi main oraz `uv` w PATH (np. ~/.local/bin).
set -euo pipefail

APP_DIR="${DEPLOY_APP_DIR:-/srv/panstwa-miasta}"
if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "Brak repozytorium git w $APP_DIR — na VPS wykonaj clone (patrz deploy/README.md §1)." >&2
  exit 1
fi
cd "$APP_DIR"

export PATH="${HOME}/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv nie znaleziony w PATH; dodaj np. ~/.local/bin do profilu lub zmiennej PATH." >&2
  exit 1
fi

# Git 2.35+ (inny użytkownik niż właściciel katalogu) — bezpieczny katalog roboczy
git config --global --add safe.directory "$APP_DIR" 2>/dev/null || true

git fetch origin
git checkout main
git pull --ff-only origin main

echo "Deploy: $(git rev-parse --short HEAD) ($(git log -1 --format=%ci))"

uv sync --frozen

if [[ "$(id -u)" -eq 0 ]]; then
  systemctl restart panstwa-miasta
else
  sudo -n systemctl restart panstwa-miasta
fi

code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)"
if [[ "$code" != "200" ]]; then
  echo "Smoke test GET / zwrócił HTTP $code (oczekiwano 200)." >&2
  exit 1
fi

echo "Deploy zakończony pomyślnie (HTTP $code)."
