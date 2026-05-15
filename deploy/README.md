# Wdrożenie na VPS (Ubuntu + Caddy + systemd)

Nie zastępuje audytu bezpieczeństwa — minimalny sensowny MVP.

## 0. Na serwerze (jako root, potem zwykły user)

- `apt update && apt upgrade -y`
- Użytkownik z sudo, logowanie kluczem SSH, `ufw` (22, 80, 443)
- [Instalacja uv](https://docs.astral.sh/uv/getting/installation/) dla użytkownika aplikacji
- `apt install -y caddy` (lub wg [dokumentacji Caddy](https://caddyserver.com/docs/install))

## 1. Kod aplikacji

```bash
sudo mkdir -p /srv/panstwa-miasta
sudo chown TWOJ_USER: /srv/panstwa-miasta
cd /srv/panstwa-miasta
git clone https://github.com/filki/panstwa-miasta.git .
uv sync
```

Baza SQLite pojawi się jako `panstwa_miasta.db` w katalogu głównym repozytorium (obok `src/`).

## 2. systemd

```bash
sed -e 's|APP_DIR|/srv/panstwa-miasta|g' -e 's|UNIX_USER|twoj_user|g' \
  deploy/panstwa-miasta.service.example | sudo tee /etc/systemd/system/panstwa-miasta.service
sudo systemctl daemon-reload
sudo systemctl enable --now panstwa-miasta
curl -sI http://127.0.0.1:8000/ | head -3
```

## 3. Caddy

Podmień domenę w `deploy/Caddyfile.example`, potem:

```bash
sudo cp deploy/Caddyfile.example /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

Caddy sam wystawi Let’s Encrypt po poprawnym DNS.

## 4. Smoke test

- Strona główna `https://twoja-domena/`
- Utworzenie pokoju, WebSocket (gra), odświeżenie w trakcie rundy
- Z maszyny z dostępem do domeny: `PROD_BASE_URL=https://panstwamiasta.com.pl ./deploy/prod-smoke-check.sh` — HTTP(S) + checklista ręczna (WS, reconnect, grace). Wyniki zapisz w issue/PR.
- Po każdym deployu z Actions: opcjonalnie na VPS ustaw `PROD_BASE_URL=https://twoja-domena` w unit systemd lub w jednorazowym `export` przed ręcznym uruchomieniem [`vps-pull-and-restart.sh`](vps-pull-and-restart.sh) — skrypt sprawdzi też publiczny HTTPS (patrz §6).

## 4.1 Checklist produkcji (hardening)

Wykonaj raz po starcie i powtórz po większych zmianach infrastruktury:

- [ ] `systemctl show panstwa-miasta -p Environment` zawiera `PM_TRUST_X_FORWARDED_FOR=1` (limity IP za Caddy).
- [ ] `WorkingDirectory` w unit = `DEPLOY_APP_DIR` / katalog z clone (domyślnie `/srv/panstwa-miasta`).
- [ ] `ufw status` — dozwolone 22, 80, 443; logowanie SSH kluczem (hasło wyłączone dla roota, jeśli możliwe).
- [ ] Cron backupu [`backup-db.sh`](backup-db.sh) + test odtworzenia kopii (`PRAGMA integrity_check`).
- [ ] Zewnętrzny monitoring (Uptime Kuma, Healthchecks.io itd.) na `https://twoja-domena/` i `/healthz` co 5–15 min (patrz §6 **Uptime Kuma**).
- [ ] Caddy z nagłówkami z [`Caddyfile.example`](Caddyfile.example) (`reload` po zmianie).
- [ ] `PM_APPEALS_LLM` **nie** ustawione na produkcji, dopóki nie ma świadomej zgody i aktualizacji polityki prywatności.
- [ ] Ćwiczenie rollbacku: `DEPLOY_APP_DIR=… ./deploy/vps-rollback.sh <rev>`.

## 5. CD z GitHub Actions (opcjonalnie)

Po każdym **pushu na `main`** z zielonym CI możesz automatycznie robić `git pull`, `uv sync --frozen` i `systemctl restart panstwa-miasta` na VPS.

Workflow: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). Skrypt na serwerze: `deploy/vps-pull-and-restart.sh` (wgrywany do `/tmp` na czas joba).

### Zmienne repozytorium

W **Settings → Secrets and variables → Actions → Variables**:

| Nazwa | Wartość |
|--------|---------|
| `DEPLOY_ENABLED` | `true` — włącza auto-deploy po zakończeniu CI na `main` (push). Ustaw w **Variables** (nie Secrets). Bez tego tylko ręczny **Run workflow**. |
| `DEPLOY_APP_DIR` | Opcjonalnie: katalog z klone repozytorium na VPS (np. `/srv/panstwa-miasta`). **Musi być zgodny** z `WorkingDirectory` w unit systemd. Puste = domyślna ścieżka ze skryptu (`/srv/panstwa-miasta`). |

### Sekrety

W **Settings → Secrets and variables → Actions → Secrets**:

| Sekret | Opis |
|--------|------|
| `DEPLOY_HOST` | IPv4 lub hostname VPS (np. `46.62.225.116`) |
| `DEPLOY_USER` | Użytkownik SSH (np. `root` lub dedykowany użytkownik z dostępem do katalogu aplikacji) |
| `DEPLOY_SSH_KEY` | Prywatny klucz OpenSSH — **tylko** do logowania runnera GitHub Actions na VPS (nie wgrywaj tego klucza na serwer). Na VPS `git pull` z **publicznego** repo zwykle działa przez `https://…` jako `origin` bez osobnego tokenu. |

### Uprawnienia na VPS

- Katalog z aplikacją musi należeć do `DEPLOY_USER` (`chown`), żeby `git pull` i `uv sync` działały.
- Jeśli `DEPLOY_USER` **nie** jest rootem, `systemctl restart` wymaga sudo bez hasła — przykład: [`deploy/SUDOERS.example`](SUDOERS.example) (`sudo visudo -f /etc/sudoers.d/...`).
- Pierwszy deploy: **Actions → Deploy → Run workflow** (gałąź `main`) — nie wymaga `DEPLOY_ENABLED`; job sprawdza obecność sekretów i uruchamia ten sam skrypt co auto-deploy.

### Uwagi

- Nazwa workflowu wyzwalającego musi być dokładnie **`CI`** (jak w `.github/workflows/ci.yml`). Job **SonarQube Cloud** jest częścią CI na `main` — jeśli Sonar padnie, **deploy się nie uruchomi** (`conclusion: success`). Napraw analizę albo tymczasowo wyłącz job Sonar w CI.
- Nie commituj sekretów do repo.

### Rozwiązywanie problemów

| Objaw | Co sprawdzić |
|--------|----------------|
| `Brak sekretu Actions` | Uzupełnij `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY`. |
| `Brak repozytorium git w ...` | Na VPS wykonaj clone do katalogu z §1 / `DEPLOY_APP_DIR`. |
| `uv nie znaleziony` | Zainstaluj `uv` dla tego samego użytkownika co SSH; skrypt dodaje `~/.local/bin` do `PATH`. |
| `sudo: a password is required` | Sudoers jak w `SUDOERS.example` albo deploy jako root (mniej zalecane). |
| Smoke test ≠ 200 | `journalctl -u panstwa-miasta -e`; Caddy / firewall; czy usługa nasłuchuje na `127.0.0.1:8000`. Przy Turso deploy czeka do 20 min na `/healthz` — 502 z Caddy = uvicorn jeszcze w `lifespan`. |
| Deploy timeout na `/healthz` | Ustaw `PM_DEPLOY_HEALTH_TIMEOUT_SEC=1200` lub `LIBSQL_*` w `/etc/panstwa-miasta.env`; unit: `TimeoutStartSec=1200` w [`panstwa-miasta.service.example`](panstwa-miasta.service.example). |
| SSH / host key | Domyślnie `appleboy/ssh-action` może akceptować nowy klucz; dla produkcji rozważ `known_hosts` (dokumentacja akcji). |

## 6. Uwagi ogólne

- Jeden proces `uvicorn` = jedna kopia limitów w RAM (`limits.py`); przy skalowaniu — osobna dyskusja.
- **Limity za Caddy:** w działającym unit systemd musi być `Environment=PM_TRUST_X_FORWARDED_FOR=1` (jak w [`panstwa-miasta.service.example`](panstwa-miasta.service.example)), inaczej rate limit widzi IP proxy zamiast klienta. Unit powinien mieć `EnvironmentFile=/etc/panstwa-miasta.env` (szablon w example) oraz `TimeoutStartSec=1200` przy Turso. Po zmianie: `sudo systemctl daemon-reload && sudo systemctl restart panstwa-miasta`.
- **Umami Cloud (opcjonalnie):** w unit systemd lub `EnvironmentFile` ustaw `UMAMI_SCRIPT_URL` i `UMAMI_WEBSITE_ID` (patrz [`env.example`](env.example)). Brak któregokolwiek = brak skryptu w HTML (dev, CI). Po deployu sprawdź pageview w panelu Umami dla `https://panstwamiasta.com.pl/`. Nie commituj ID do repo.
- **Turso (libSQL):** w `EnvironmentFile` ustaw `LIBSQL_URL` i `LIBSQL_AUTH_TOKEN` (embedded replica — lokalny plik w `APP_DIR`, zapisy na primary w chmurze; patrz [`env.example`](env.example)). Przed pierwszym włączeniem na istniejącym VPS zaimportuj bieżący `panstwa_miasta.db` do Turso (`turso db import …`) albo zaakceptuj świeży seed przy pustej bazie w chmurze. Nie commituj tokenów.

#### Turso: import i cutover (checklista)

Szczegółowy plan krok po kroku (okno serwisowe, czas `/healthz`, rollback po 502): [`TURSO-cutover.md`](TURSO-cutover.md).

1. Backup na VPS: `DEPLOY_APP_DIR=/srv/panstwa-miasta deploy/backup-db.sh`.
2. `turso auth login` (lub `--headless`) na maszynie z CLI; import: `turso db import <baza> /ścieżka/panstwa_miasta.db`.
3. Zweryfikuj `COUNT(*)` w Turso vs kopia źródłowa (słowniki + `rooms` / `players` / `game_transcripts`).
4. W `EnvironmentFile`: `LIBSQL_URL`, `LIBSQL_AUTH_TOKEN`, opcjonalnie `LIBSQL_SYNC_INTERVAL=60` (token tylko na serwerze; po wycieku — rotacja w panelu Turso).
5. Cutover: `systemctl stop panstwa-miasta`; usuń lokalny plik repliki i pliki towarzyszące (`panstwa_miasta.db`, `panstwa_miasta.db-info`, `-wal`, `-shm`); nie zostawiaj samego pliku SQLite bez metadanych libSQL — przy starcie embedded replica synchronizuje się z primary. Zachowaj kopię `panstwa_miasta.db.pre-turso`.
6. `systemctl start panstwa-miasta`; smoke: `GET http://127.0.0.1:8000/healthz`, publiczny HTTPS, krótka gra.
7. Import i migracje: **jeden** proces zapisu naraz (bez równoległych klientów `libsql` / wielu pipeline HTTP).

**Rollback:** usuń linie `LIBSQL_*` z `EnvironmentFile`, przywróć `panstwa_miasta.db` z kopii, usuń pliki metadanych repliki, `systemctl restart panstwa-miasta`.

**Bramka RAG:** kolejka weryfikacji słów (`PM_RAG_QUEUE_ENABLED`, worker n8n) włączana dopiero po stabilnym cutoverze na Turso i smoke teście rollbacku. Porównanie liczności tabel: `uv run python scripts/db_table_counts.py` na kopii źródłowej i na replice po starcie.

**Staging RAG:** ustaw `PM_WORDS_WORKER_TOKEN`, włącz workflow w n8n (`deploy/n8n/workflows/`), na stagingu `PM_RAG_QUEUE_ENABLED=1`, smoke: zgłoszenie słowa → pending → decyzja workera → `POST /api/words/check-reason`. Produkcja dopiero po aktualizacji polityki prywatności.

### Backup SQLite

Skrypt [`backup-db.sh`](backup-db.sh) — `sqlite3 .backup`, rotacja domyślnie 14 dni (`PM_DB_BACKUP_KEEP_DAYS`), katalog `backups/` w `APP_DIR` (lub `PM_DB_BACKUP_DIR`).

Przykład cron (codziennie 03:15 UTC, użytkownik aplikacji):

```cron
15 3 * * * DEPLOY_APP_DIR=/srv/panstwa-miasta /srv/panstwa-miasta/deploy/backup-db.sh >>/var/log/panstwa-miasta-backup.log 2>&1
```

Po pierwszym uruchomieniu sprawdź `PRAGMA integrity_check` na kopii (skrypt wypisuje wynik).

### Uptime Kuma (self-host na VPS)

Instalacja poza katalogiem aplikacji (np. `/opt/uptime-kuma`), Docker Compose z [`uptime-kuma/docker-compose.example.yml`](uptime-kuma/docker-compose.example.yml) — port `127.0.0.1:3001` (bez publicznego portu poza Caddy).

- **Panel:** subdomena `status.twoja-domena.pl` w Caddy (`reverse_proxy 127.0.0.1:3001`); rekord DNS **A** na IP serwera przed pierwszym TLS. Bez DNS: tunel SSH `ssh -L 3001:127.0.0.1:3001 user@vps` i `http://127.0.0.1:3001`.
- **Monitory:** `https://twoja-domena/` (HTTP 200) oraz `https://twoja-domena/healthz` (keyword `ok` lub JSON), interwał 5–10 min.
- **Alerty:** co najmniej jeden kanał (webhook, e-mail, Telegram); test z panelu po konfiguracji.
- **Logi:** `cd /opt/uptime-kuma && docker compose logs -f`.
- Hasło admina: poza repo (np. `/root/.uptime-kuma-admin.pass` na VPS).

### Obserwacja deployu i rollback

- Po merge na `main`: job **Deploy** w Actions + smoke `GET http://127.0.0.1:8000/` i `GET /healthz` w [`vps-pull-and-restart.sh`](vps-pull-and-restart.sh). Opcjonalnie ustaw `PROD_BASE_URL=https://twoja-domena` przed deployem — skrypt sprawdzi też publiczny HTTPS na `/` i `/healthz`.
- **Zewnętrzny ping** (Uptime Kuma, Healthchecks.io itd.) na publiczny URL i `/healthz` co 5–15 min — poza samym workflow.
- **Smoke po release:** `PROD_BASE_URL=https://twoja-domena ./deploy/prod-smoke-check.sh` (z maszyny z dostępem do domeny); wynik w issue/PR.
- **Rollback:** na VPS `git log --oneline -5` → `DEPLOY_APP_DIR=… ./deploy/vps-rollback.sh <rev>` (checkout rewizji, `uv sync --frozen`, restart, smoke lokalny). Alternatywnie ręcznie: `git checkout <rev>` w `APP_DIR`, potem `uv sync --frozen` i `systemctl restart panstwa-miasta`.

### Nagłówki bezpieczeństwa (Caddy)

Przykład w [`Caddyfile.example`](Caddyfile.example): HSTS, `nosniff`, `Referrer-Policy`, `Permissions-Policy`, `frame-ancestors 'none'`. Po zmianie: `sudo systemctl reload caddy`. Pełne **CSP** (Google Fonts, CDN confetti, przyszła analityka) — osobny krok z whitelistą.

### Odwołania i LLM

- Odwołania po grze wymagają **tokenu** wydanego po `game_over` (WebSocket `appeal_token`); bez niego API zwraca `401`.
- **`PM_APPEALS_LLM`** domyślnie wyłączone na produkcji; włącz tylko świadomie i zaktualizowaną polityką prywatności.

## 7. Wiele workerów / Redis (opcjonalnie)

Stan pokoju (`manager.rooms`) żyje w pamięci jednego procesu. Przy **kilku instancjach** `uvicorn` za load balancerem (sticky sessions nie gwarantują tego samego workera na reconnect) potrzebny jest **współdzielony magazyn** stanu pokoju.

**Redis (szkic):** klucz `room:{room_id}` → JSON snapshot (scores, host, `current_round`, `is_playing`, `current_letter`, `answers_received`, kolejka liter — tylko to, co musi przeżyć proces). TTL np. 24 h. Zapis **write-through** po każdej istotnej zmianie; przy braku pokoju w RAM — odczyt snapshotu i odbudowa `Room`. **Redis Pub/Sub** (kanał np. `room:{id}`) do broadcastu zdarzeń między workerami zamiast samego in-process `room.broadcast`.

Operacyjnie: ten sam VPC co VPS, `AUTH`, limity pamięci, persistence (AOF/RDB) według polityki. W Dockerze: osobny serwis `redis` + zmienne środowiskowe URL w aplikacji. Na Hetznerze typowo mały VPS lub managed Redis — koszt vs złożoność.

**Uwaga:** nawet z Redisem trzeba utrzymać poprawny front (np. nie zerować rankingu w `onopen` przed `score_update`).
