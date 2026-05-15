# Plan cutoveru Turso (libSQL embedded replica)

Dokument operacyjny na **jednorazowe** przełączenie produkcji z lokalnego SQLite na Turso.
Nie uruchamiaj cutoveru bez okna serwisowego i ćwiczonego rollbacku. Po nieudanej próbie (502
za Caddy) produkcja wróciła na czysty SQLite — ten plan uwzględnia wnioski z tamtego incydentu.

## Cel i zakres

- **Cel:** jeden primary w Turso, na VPS embedded replica (`panstwa_miasta.db` + sync do chmury).
- **Poza zakresem:** włączenie kolejki RAG (`PM_RAG_QUEUE_ENABLED`), n8n na publicznym HTTPS,
  zmiany wieloprocesowe / Redis.
- **Bramka:** stabilny Turso + smoke + ćwiczenie rollbacku **przed** włączeniem RAG na produkcji.

## Architektura (skrót)

1. `lifespan` w `main.py` przed nasłuchem: `init_db()` → `reload_*` → `load_from_db()`.
2. Przy `LIBSQL_URL` + `LIBSQL_AUTH_TOKEN` `db_backend.connect()` otwiera replikę libSQL
   (`sync_url`, `auth_token`, `sync_interval`, lokalna ścieżka = `DB_PATH`).
3. Caddy proxy na `127.0.0.1:8000` — jeśli uvicorn nie wstał, zewnętrznie widać **502**, mimo że
   `systemctl` może pokazywać `active`.

## Faza 0 — przygotowanie (bez zmiany produkcji)

| Krok | Działanie | Kryterium sukcesu |
|------|-----------|-------------------|
| 0.1 | Okno serwisowe (15–30 min), komunikat „krótka przerwa” opcjonalnie | Zatwierdzone |
| 0.2 | `DEPLOY_ENABLED=false` w GitHub Variables na czas cutoveru | Brak auto-deploy w trakcie |
| 0.3 | Rotacja `LIBSQL_AUTH_TOKEN` w panelu Turso (stary token z czatu / logów unieważniony) | Nowy token tylko w `EnvironmentFile` na VPS |
| 0.4 | Backup: `DEPLOY_APP_DIR=/srv/panstwa-miasta deploy/backup-db.sh` | Kopia w `backups/`, `PRAGMA integrity_check` = ok |
| 0.5 | Kopia ręczna: `cp panstwa_miasta.db panstwa_miasta.db.pre-turso-$(date -u +%Y%m%d)` | Plik poza katalogiem repliki po cutoverze |
| 0.6 | Baseline liczności na VPS (SQLite): `cd /srv/panstwa-miasta && uv run python scripts/db_table_counts.py` | JSON zapisany (np. `counts-pre.json`) |
| 0.7 | Uptime / alert: monitoring na `/healthz` z dłuższym progiem na czas restartu | Gotowy kanał alertów |

**Oczekiwane baseline (orientacyjnie):** `countries` 205, `cities` ~31k, `names` 1455, `jobs` 1450;
`rooms` / `players` / `game_transcripts` — wartości operacyjne; `dictionary_suggestions` może być 0.

## Faza 1 — primary w Turso = kopia produkcji

Wykonaj na maszynie z **Turso CLI** (laptop/WSL) lub importem z panelu — na VPS CLI bywa
niewygodne (`turso auth login --token` nie zawsze wspierane).

1. `turso auth login` (interaktywnie lub headless według aktualnej dokumentacji Turso).
2. Utwórz bazę lub użyj istniejącej (np. `panstwa-miasta-prod`).
3. Import z kopii z VPS (scp `panstwa_miasta.db` lub plik z `backup-db.sh`):
   `turso db import <nazwa-bazy> /ścieżka/panstwa_miasta.db`
4. Zweryfikuj `COUNT(*)` w Turso vs `counts-pre.json` (te same tabele co
   `scripts/db_table_counts.py`).
5. **Nie** uruchamiaj równolegle drugiego procesu aplikacji z zapisem do tego samego primary.

## Faza 2 — replika na stagingu (zalecane)

1. Klon repo, `uv sync`, `LIBSQL_*` w `.env` (lokalnie, nie w repo).
2. Usuń lokalne pliki repliki (`panstwa_miasta.db`, `*-info`, `-wal`, `-shm`) przed pierwszym startem.
3. Start aplikacji; **czekaj na `/healthz`** (patrz § Czas startu) — nie ufaj samemu `active` w systemd.
4. `uv run python scripts/db_table_counts.py` — zgodność z Fazą 1.
5. Smoke: landing, pokój, WebSocket, jedna runda, `/healthz`.
6. Rollback ćwiczeniowy: wyłącz `LIBSQL_*`, przywróć plik SQLite, restart — powtórz raz.

## Faza 3 — konfiguracja VPS (przed restartem z Turso)

Plik środowiska (np. `/etc/panstwa-miasta.env` — ścieżka z unit systemd):

```bash
LIBSQL_URL=libsql://<twoja-baza>.turso.io
LIBSQL_AUTH_TOKEN=<token z panelu Turso>
# opcjonalnie:
# LIBSQL_SYNC_INTERVAL=60
```

Unit musi mieć `EnvironmentFile=` wskazujący ten plik. **Nie** commituj tokenów.

**Wyłącz na czas cutoveru:** `PM_RAG_QUEUE_ENABLED` (brak lub `0`).

## Faza 4 — cutover produkcji (okno serwisowe)

Kolejność ma znaczenie — nie pomijaj usuwania metadanych repliki.

```bash
sudo systemctl stop panstwa-miasta
cd /srv/panstwa-miasta
# Zachowaj kopię — już powinna istnieć z Fazy 0
ls -la panstwa_miasta.db.pre-turso*
# Usuń replikę i sidecary (nie zostawiaj „gołego” SQLite bez metadanych libSQL)
rm -f panstwa_miasta.db panstwa_miasta.db-info panstwa_miasta.db-wal panstwa_miasta.db-shm
# Upewnij się, że LIBSQL_* są w EnvironmentFile
sudo systemctl start panstwa-miasta
```

### Czas startu i `/healthz`

Pierwszy start z pustą repliką: synchronizacja z primary + `init_db()` (DDL; seedy tylko gdy
tabele puste — po imporcie do Turso bez ~31k redundantnych INSERT) + `reload_*` (duże cache w RAM)
+ `load_from_db()` — na małym VPS **wiele minut** jest realne.

- Poll: `deploy/turso-poll-healthz.sh` lub `curl -sf http://127.0.0.1:8000/healthz` co 10 s,
  **do 15–20 min** pierwszego cutoveru.
- Równolegle: `journalctl -u panstwa-miasta -f` — szukaj `Application startup` / `Startup completed`.
- Dopiero po `Startup completed` i `healthz` → test publiczny HTTPS.

Po cutoverze: `uv run python scripts/db_table_counts.py` → porównaj z `counts-pre.json`.

## Faza 5 — smoke po cutoverze

1. `GET https://panstwamiasta.com.pl/healthz` — `ok`.
2. `deploy/prod-smoke-check.sh` z `PROD_BASE_URL=https://panstwamiasta.com.pl`.
3. Gra: utworzenie pokoju, WS, runda, reconnect.
4. Backup: upewnij się, że cron `backup-db.sh` nadal ma sens (replika lokalna = plik do `.backup`).

## Rollback (produkcja)

Wykonaj **przed** zamknięciem okna, jeśli `healthz` nie wraca w limicie czasu lub smoke pada.

```bash
sudo systemctl stop panstwa-miasta
cd /srv/panstwa-miasta
# Usuń LIBSQL_* z EnvironmentFile (komentarz lub usunięcie linii)
sudo editor /etc/panstwa-miasta.env   # lub faktyczna ścieżka
rm -f panstwa_miasta.db panstwa_miasta.db-info panstwa_miasta.db-wal panstwa_miasta.db-shm
cp panstwa_miasta.db.pre-turso-YYYYMMDD panstwa_miasta.db
sudo systemctl start panstwa-miasta
curl -sf http://127.0.0.1:8000/healthz
```

Jeśli `systemctl stop` wisi: po krótkim czasie `kill` procesu uvicorn (jak przy poprzednim
incydencie), potem przywróć pliki i start.

Po rollbacku: `DEPLOY_ENABLED` z powrotem `true` gdy stan stabilny.

## Znane pułapki (z kodu i z produkcji)

| Objaw | Przyczyna | Mitigacja |
|--------|-----------|-----------|
| 502, Caddy OK | Uvicorn jeszcze w `lifespan` | Czekaj na `/healthz`, nie na `systemctl is-active` |
| `TypeError` na `async with db.execute` | libSQL vs aiosqlite | `db_backend.py` — wrapper z `contextmanager` |
| `fetchall()` / DDL | Puste wyniki na libSQL | `_rows_from_cursor` w `db_backend.py` |
| Niespójna replika | Stary plik SQLite + nowe `LIBSQL_*` | Zawsze usuń db + sidecary przed pierwszym startem repliki |
| Długi cold start | Sync repliki + `reload_*` przy każdym starcie | `init_db` pomija seed gdy tabela niepusta; deploy: 20 min poll `/healthz`; pierwszy cutover nadal długi |
| Token w czacie / logu | Wyciek | Rotacja w Turso, tylko `EnvironmentFile` |
| Dwa writery | Import + działająca app na tym samym primary | Jeden proces zapisu na cutover |

## Po stabilnym Turso

1. Przywróć `DEPLOY_ENABLED=true`.
2. Utrzymuj backup lokalnej repliki (`backup-db.sh`).
3. Dopiero potem: staging RAG (`PM_WORDS_WORKER_TOKEN`, n8n, `PM_RAG_QUEUE_ENABLED=1`), E2E,
   aktualna polityka prywatności, produkcja RAG na końcu.
4. Opcjonalnie: DNS + Caddy dla `n8n.panstwamiasta.com.pl` (osobny dokument w `deploy/n8n/`).

## Checklist jednostronicowa (do wydruku)

- [ ] Backup + `counts-pre.json`
- [ ] Import do Turso + weryfikacja COUNT
- [ ] (Zalecane) staging z `LIBSQL_*` + smoke + rollback ćwiczeniowy
- [ ] `DEPLOY_ENABLED=false`
- [ ] Nowy token Turso w `EnvironmentFile`
- [ ] `stop` → usunięcie repliki/sidecarów → `start`
- [ ] Poll `/healthz` do 15–20 min
- [ ] `db_table_counts.py` po starcie = baseline
- [ ] `prod-smoke-check.sh` + gra ręczna
- [ ] Rollback przetestowany lub potwierdzony zbędny
- [ ] `DEPLOY_ENABLED=true`
- [ ] RAG nadal wyłączone do osobnej decyzji

Skrót w [`README.md`](README.md) § Turso; porównanie tabel: `scripts/db_table_counts.py`.
