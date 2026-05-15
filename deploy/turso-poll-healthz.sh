#!/usr/bin/env bash
# Poll lokalnego /healthz po restarcie (cutover Turso). Użycie na VPS w oknie serwisowym.
set -euo pipefail

TIMEOUT_SEC="${1:-1200}"
INTERVAL_SEC="${2:-10}"
URL="${PM_HEALTHZ_URL:-http://127.0.0.1:8000/healthz}"

echo "Polling ${URL} co ${INTERVAL_SEC}s (max ${TIMEOUT_SEC}s)..."
deadline=$((SECONDS + TIMEOUT_SEC))
while (( SECONDS < deadline )); do
  if curl -sf "$URL" >/dev/null 2>&1; then
    echo "OK  $(curl -s "$URL")"
    exit 0
  fi
  sleep "$INTERVAL_SEC"
done

echo "Timeout: /healthz nie odpowiedział w ${TIMEOUT_SEC}s." >&2
echo "--- journalctl -u panstwa-miasta (ostatnie 80 linii) ---" >&2
journalctl -u panstwa-miasta -n 80 --no-pager >&2 || true
exit 1
