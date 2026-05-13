#!/usr/bin/env bash
# Automatyczny smoke HTTP(S) produkcji + checklista ręczna (WS, reconnect, grace).
# Użycie: PROD_BASE_URL=https://panstwamiasta.com.pl ./deploy/prod-smoke-check.sh
set -euo pipefail

BASE="${PROD_BASE_URL:-https://panstwamiasta.com.pl}"
PATHS=(/ /polityka-prywatnosci /cookies /regulamin /manifest.json /sw.js)

fail=0
for path in "${PATHS[@]}"; do
  url="${BASE%/}${path}"
  code="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 15 "$url" || echo "000")"
  if [[ "$code" == "200" ]]; then
    echo "OK  $code  $url"
  else
    echo "FAIL $code  $url" >&2
    fail=1
  fi
done

cat <<'EOF'

--- Ręcznie (2 urządzenia lub telefon + desktop) ---
[ ] Landing → utworzenie pokoju → WebSocket → runda → wyniki
[ ] Odświeżenie w rundzie: ta sama litera (resume), bez ponownego losu
[ ] Krótki brak sieci: auto-reconnect, ranking bez zerowania w onopen
[ ] Wszyscy wypadają na chwilę: powrót w grace — punkty z SQLite; runda w RAM może nie wrócić
[ ] DEPLOY_APP_DIR na VPS = WorkingDirectory w systemd (domyślnie /srv/panstwa-miasta)

Zapisz wyniki w issue/PR (co przeszło / co nie).
EOF

exit "$fail"
