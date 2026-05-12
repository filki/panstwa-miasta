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

## Uwagi

- Jeden proces `uvicorn` = jedna kopia limitów w RAM (`limits.py`); przy skalowaniu — osobna dyskusja.
- Backup: kopiuj `panstwa_miasta.db` (np. cron + `sqlite3 .backup`).
