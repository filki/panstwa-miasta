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

uv sync --frozen --extra dev

echo "Buduję CSS (Tailwind)..."
npm ci --no-audit --no-fund --silent 2>&1
npm run css:build

if [[ "$(id -u)" -eq 0 ]]; then
  systemctl restart panstwa-miasta
else
  sudo -n systemctl restart panstwa-miasta
fi

# Turso / libSQL lub pierwszy seed animal_norms+plant_norms (~20k wierszy) — startup może trwać wiele minut.
if [[ -n "${PM_DEPLOY_HEALTH_TIMEOUT_SEC:-}" ]]; then
  health_timeout="${PM_DEPLOY_HEALTH_TIMEOUT_SEC}"
elif [[ -f /etc/panstwa-miasta.env ]] && grep -qE '^LIBSQL_URL=' /etc/panstwa-miasta.env 2>/dev/null; then
  health_timeout=1200
elif [[ -f scripts/seed_data/animals_norms.jsonl.gz ]]; then
  health_timeout=1200
else
  health_timeout=120
fi

echo "Czekam na /healthz (timeout ${health_timeout}s, co 10s)..."
deadline=$((SECONDS + health_timeout))
health_code="000"
while (( SECONDS < deadline )); do
  health_code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/healthz 2>/dev/null || echo "000")"
  if [[ "$health_code" == "200" ]]; then
    break
  fi
  sleep 10
done

if [[ "$health_code" != "200" ]]; then
  echo "Smoke test GET /healthz zwrócił HTTP $health_code po ${health_timeout}s (oczekiwano 200)." >&2
  echo "--- journalctl -u panstwa-miasta (ostatnie 80 linii) ---" >&2
  journalctl -u panstwa-miasta -n 80 --no-pager >&2 || true
  exit 1
fi

code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)"
if [[ "$code" != "200" ]]; then
  echo "Smoke test GET / zwrócił HTTP $code (oczekiwano 200)." >&2
  exit 1
fi

if [[ -n "${PROD_BASE_URL:-}" ]]; then
  public_base="${PROD_BASE_URL%/}"
  for path in / /healthz; do
    pub_code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 15 "${public_base}${path}" || echo "000")"
    if [[ "$pub_code" != "200" ]]; then
      echo "Smoke HTTPS ${public_base}${path} zwrócił HTTP $pub_code (oczekiwano 200)." >&2
      exit 1
    fi
    echo "OK  $pub_code  ${public_base}${path}"
  done
fi

echo "Deploy zakończony pomyślnie (lokalny HTTP $code, /healthz $health_code)."
