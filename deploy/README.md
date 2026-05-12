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

## 5. CD z GitHub Actions (opcjonalnie)

Po każdym **pushu na `main`** z zielonym CI możesz automatycznie robić `git pull`, `uv sync --frozen` i `systemctl restart panstwa-miasta` na VPS.

Workflow: [`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml). Skrypt na serwerze: `deploy/vps-pull-and-restart.sh` (wgrywany do `/tmp` na czas joba).

### Zmienne repozytorium

W **Settings → Secrets and variables → Actions → Variables**:

| Nazwa | Wartość |
|--------|---------|
| `DEPLOY_ENABLED` | `true` — włącza auto-deploy po zakończeniu CI na `main` (push). Bez tego tylko ręczny **Run workflow**. |
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
| Smoke test ≠ 200 | `journalctl -u panstwa-miasta -e`; Caddy / firewall; czy usługa nasłuchuje na `127.0.0.1:8000`. |
| SSH / host key | Domyślnie `appleboy/ssh-action` może akceptować nowy klucz; dla produkcji rozważ `known_hosts` (dokumentacja akcji). |

## 6. Uwagi ogólne

- Jeden proces `uvicorn` = jedna kopia limitów w RAM (`limits.py`); przy skalowaniu — osobna dyskusja.
- Backup: kopiuj `panstwa_miasta.db` (np. cron + `sqlite3 .backup`).

## 7. Wiele workerów / Redis (opcjonalnie)

Stan pokoju (`manager.rooms`) żyje w pamięci jednego procesu. Przy **kilku instancjach** `uvicorn` za load balancerem (sticky sessions nie gwarantują tego samego workera na reconnect) potrzebny jest **współdzielony magazyn** stanu pokoju.

**Redis (szkic):** klucz `room:{room_id}` → JSON snapshot (scores, host, `current_round`, `is_playing`, `current_letter`, `answers_received`, kolejka liter — tylko to, co musi przeżyć proces). TTL np. 24 h. Zapis **write-through** po każdej istotnej zmianie; przy braku pokoju w RAM — odczyt snapshotu i odbudowa `Room`. **Redis Pub/Sub** (kanał np. `room:{id}`) do broadcastu zdarzeń między workerami zamiast samego in-process `room.broadcast`.

Operacyjnie: ten sam VPC co VPS, `AUTH`, limity pamięci, persistence (AOF/RDB) według polityki. W Dockerze: osobny serwis `redis` + zmienne środowiskowe URL w aplikacji. Na Hetznerze typowo mały VPS lub managed Redis — koszt vs złożoność.

**Uwaga:** nawet z Redisem trzeba utrzymać poprawny front (np. nie zerować rankingu w `onopen` przed `score_update`).
