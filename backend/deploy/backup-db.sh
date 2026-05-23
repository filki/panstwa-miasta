#!/usr/bin/env bash
# Kopia panstwa_miasta.db (cron na VPS). Wymaga sqlite3 w PATH.
set -euo pipefail

APP_DIR="${DEPLOY_APP_DIR:-/srv/panstwa-miasta}"
DB="${APP_DIR}/panstwa_miasta.db"
BACKUP_DIR="${PM_DB_BACKUP_DIR:-${APP_DIR}/backups}"
KEEP_DAYS="${PM_DB_BACKUP_KEEP_DAYS:-14}"

if [[ ! -f "$DB" ]]; then
  echo "Brak bazy: $DB" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dest="${BACKUP_DIR}/panstwa_miasta-${stamp}.db"
sqlite3 "$DB" ".backup '${dest}'"
echo "Backup: $dest"

find "$BACKUP_DIR" -maxdepth 1 -name 'panstwa_miasta-*.db' -mtime +"${KEEP_DAYS}" -delete 2>/dev/null || true

# Suchy test odtworzenia (otwarcie kopii)
sqlite3 "$dest" "PRAGMA integrity_check;" | head -1
