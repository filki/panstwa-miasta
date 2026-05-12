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

### Zmienna repozytorium

W **Settings → Secrets and variables → Actions → Variables** dodaj:

| Nazwa | Wartość |
|--------|---------|
| `DEPLOY_ENABLED` | `true` |

Bez tej zmiennej deploy **nie** uruchomi się po CI (nie blokuje merge). Ręczne **Run workflow** zawsze może odpalić deploy (patrz poniżej).

### Sekrety

W **Settings → Secrets and variables → Actions → Secrets**:

| Sekret | Opis |
|--------|------|
| `DEPLOY_HOST` | IPv4 lub hostname VPS (np. `46.62.225.116`) |
| `DEPLOY_USER` | Użytkownik SSH (np. `root` lub dedykowany `deploy`) |
| `DEPLOY_SSH_KEY` | Prywatny klucz OpenSSH — **tylko** do logowania runnera GitHub Actions na VPS (nie wgrywaj tego klucza na serwer). Na VPS `git pull` z **publicznego** repo zwykle działa przez `https://…` jako `origin` bez osobnego tokenu. |
| `DEPLOY_APP_DIR` | Opcjonalnie: katalog aplikacji (domyślnie na VPS zakładamy `/var/www/panstwa-miasta`). Puste = domyślna ścieżka ze skryptu |

Skrypt na serwerze: `deploy/vps-pull-and-restart.sh` (kopiowany do `/tmp` podczas joba).

**Uprawnienia:** jeśli `DEPLOY_USER` nie jest rootem, na VPS ustaw **passwordless sudo** tylko dla `systemctl restart panstwa-miasta` (lub uruchamiaj skrypt jako root — mniej elegancko).

**Pierwszy kontakt SSH:** przy pierwszym połączeniu rozważ `ssh-keyscan` i wpisanie host key do sekretu albo polityki `KnownHosts` w runnerze — zależnie od wersji `appleboy/*` domyślne zachowanie może akceptować nowy klucz (`accept-new`).

### Ręczny deploy

**Actions → Deploy → Run workflow** (gałąź `main`) — odpala ten sam skrypt bez czekania na `DEPLOY_ENABLED` (przydatne przed włączeniem automatyzacji).

- Workflow **Deploy** podpina się pod zakończenie workflowu **CI** na gałęzi `main` (`workflow_run`). Nazwa workflowu musi być dokładnie **`CI`** (jak w `.github/workflows/ci.yml`).
- Nie commituj sekretów do repo.

## 6. Uwagi ogólne

- Jeden proces `uvicorn` = jedna kopia limitów w RAM (`limits.py`); przy skalowaniu — osobna dyskusja.
- Backup: kopiuj `panstwa_miasta.db` (np. cron + `sqlite3 .backup`).

## 7. Wiele workerów / Redis (opcjonalnie)

Stan pokoju (`manager.rooms`) żyje w pamięci jednego procesu. Przy **kilku instancjach** `uvicorn` za load balancerem (sticky sessions nie gwarantują tego samego workera na reconnect) potrzebny jest **współdzielony magazyn** stanu pokoju.

**Redis (szkic):** klucz `room:{room_id}` → JSON snapshot (scores, host, `current_round`, `is_playing`, `current_letter`, `answers_received`, kolejka liter — tylko to, co musi przeżyć proces). TTL np. 24 h. Zapis **write-through** po każdej istotnej zmianie; przy braku pokoju w RAM — odczyt snapshotu i odbudowa `Room`. **Redis Pub/Sub** (kanał np. `room:{id}`) do broadcastu zdarzeń między workerami zamiast samego in-process `room.broadcast`.

Operacyjnie: ten sam VPC co VPS, `AUTH`, limity pamięci, persistence (AOF/RDB) według polityki. W Dockerze: osobny serwis `redis` + zmienne środowiskowe URL w aplikacji. Na Hetznerze typowo mały VPS lub managed Redis — koszt vs złożoność.

**Uwaga:** nawet z Redisem trzeba utrzymać poprawny front (np. nie zerować rankingu w `onopen` przed `score_update`).
