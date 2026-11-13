#!/usr/bin/env bash
# NOVA: idempotent install/update. Safe to run any number of times.
set -euo pipefail
APP=/opt/nova; ENV=$APP/.env; DOMAIN=nova.89-208-113-147.sslip.io
REPORT=$(mktemp); STATUS=ok
log(){ echo "- $*" | tee -a "$REPORT"; }
fail(){ STATUS=fail; log "ОШИБКА: $*"; }
echo "# Установка NOVA $(date -u '+%Y-%m-%d %H:%M UTC')" > "$REPORT"; echo >> "$REPORT"
cd "$APP"; log "Версия: $(git log -1 --format='%h %s')"

# --- secrets and settings ---
touch "$ENV"; chmod 600 "$ENV"
setv(){ grep -q "^$1=" "$ENV" || echo "$1=$2" >> "$ENV"; }
getv(){ { grep "^$1=" "$ENV" || true; } | head -1 | cut -d= -f2-; }
setv JWT_SECRET "$(openssl rand -hex 32)"
setv WEBHOOK_SECRET "$(openssl rand -hex 24)"
setv DB_PASS "$(openssl rand -hex 16)"
if ! grep -q "^PORT=" "$ENV"; then P=8795; while ss -ltn | grep -q ":$P "; do P=$((P+1)); done; echo "PORT=$P" >> "$ENV"; fi
PORT=$(getv PORT); DB_PASS=$(getv DB_PASS)
setv DATABASE_URL "postgresql+asyncpg://nova:$DB_PASS@127.0.0.1:5432/nova"
setv REDIS_URL "redis://127.0.0.1:6379/5"
setv PUBLIC_URL "https://$DOMAIN"
setv STORAGE_DIR "$APP/storage"
setv STATIC_DIR "$APP/frontend/dist"
setv BOT_USERNAME "NovaAI_Agent"
[ -n "$(getv BOT_TOKEN)" ] || fail "нет BOT_TOKEN в $ENV"
[ -n "$(getv OPENROUTER_KEY)" ] || fail "нет OPENROUTER_KEY в $ENV"
[ -n "$(getv KIE_KEY)" ] || log "Ключа Kie.ai пока нет — нужен с этапа 2 (видео)"
[ -n "$(getv CRYPTO_PAY_TOKEN)" ] && log "Оплата криптой: токен есть" || log "Оплата криптой: токена нет"
[ -n "$(getv YOOKASSA_SHOP_ID)" ] && [ -n "$(getv YOOKASSA_SECRET)" ] && log "ЮKassa: ключи есть (магазин $(getv YOOKASSA_SHOP_ID))" || log "ЮKassa: ключей нет"
mkdir -p "$APP/storage"; chown -R www-data:www-data "$APP/storage" 2>/dev/null || true; chmod 755 "$APP/storage"

# --- system packages (only what is missing) ---
need=""
command -v psql >/dev/null || need="$need postgresql"
command -v redis-server >/dev/null || need="$need redis-server"
command -v nginx >/dev/null || need="$need nginx"
command -v certbot >/dev/null || need="$need certbot python3-certbot-nginx"
python3 -c "import venv, ensurepip" 2>/dev/null || need="$need python3-venv"
command -v ffmpeg >/dev/null || need="$need ffmpeg"
if [ -n "$need" ]; then DEBIAN_FRONTEND=noninteractive apt-get update -q && DEBIAN_FRONTEND=noninteractive apt-get install -y -q $need >/dev/null; log "Поставлены пакеты:$need"; fi
systemctl enable --now postgresql redis-server >/dev/null 2>&1 || true

# --- database ---
sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='nova'" | grep -q 1 || sudo -u postgres psql -qc "CREATE ROLE nova LOGIN PASSWORD '$DB_PASS'"
sudo -u postgres psql -qc "ALTER ROLE nova PASSWORD '$DB_PASS'" >/dev/null
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='nova'" | grep -q 1 || sudo -u postgres createdb -O nova nova
log "База данных: готова"

# --- python ---
[ -x "$APP/venv/bin/python" ] || python3 -m venv "$APP/venv"
REQ_HASH=$(sha256sum backend/requirements.txt | cut -c1-16)
if [ "$(cat "$APP/venv/.req" 2>/dev/null)" != "$REQ_HASH" ]; then
  "$APP/venv/bin/pip" install -q --upgrade pip >/dev/null && "$APP/venv/bin/pip" install -q -r backend/requirements.txt && echo "$REQ_HASH" > "$APP/venv/.req"
  log "Зависимости Python: обновлены"
fi

# --- services ---
cat > /etc/systemd/system/nova-api.service << UNIT
[Unit]
Description=NOVA API
After=network.target postgresql.service redis-server.service
[Service]
WorkingDirectory=$APP/backend
EnvironmentFile=$ENV
ExecStart=$APP/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port $PORT --workers 2 --proxy-headers --timeout-graceful-shutdown 10
User=www-data
Group=www-data
Restart=always
RestartSec=3
MemoryMax=700M
[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/nova-worker.service << UNIT
[Unit]
Description=NOVA worker
After=network.target postgresql.service redis-server.service
[Service]
WorkingDirectory=$APP/backend
EnvironmentFile=$ENV
ExecStart=$APP/venv/bin/arq app.worker.WorkerSettings
User=www-data
Group=www-data
Restart=always
RestartSec=5
MemoryMax=500M
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
# --- admin: the very first NOVA user becomes the admin when none is set ---
if [ -z "$(getv ADMIN_TG_IDS)" ]; then
  FIRST=$(sudo -u postgres psql -d nova -tAc "SELECT tg_id FROM users ORDER BY id LIMIT 1" 2>/dev/null | tr -d ' ')
  if [ -n "$FIRST" ]; then sed -i '/^ADMIN_TG_IDS=/d' "$ENV"; echo "ADMIN_TG_IDS=$FIRST" >> "$ENV"; fi
fi
ADM=$(getv ADMIN_TG_IDS)
if [ -n "$ADM" ]; then
  AN=$(sudo -u postgres psql -d nova -tAc "SELECT coalesce(nullif(username,''), first_name) FROM users WHERE tg_id IN ($ADM) LIMIT 3" 2>/dev/null | paste -sd, -)
  log "Админ: ${AN:-$ADM}"
else
  log "Админ: пока никого — откройте бота и нажмите Старт, затем повторите установку"
fi
systemctl enable nova-api nova-worker >/dev/null 2>&1
systemctl restart nova-api nova-worker

# --- nginx + https ---
SITE=/etc/nginx/sites-available/nova
cat > "$SITE" << NGX
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 25m;
    location /files/ { alias $APP/storage/; add_header Cache-Control "public, max-age=2592000"; add_header X-Content-Type-Options nosniff; }
    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection \$http_connection;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
NGX
ln -sf "$SITE" /etc/nginx/sites-enabled/nova
if [ -f /etc/letsencrypt/live/$DOMAIN/fullchain.pem ]; then
  certbot install --nginx -d "$DOMAIN" --cert-name "$DOMAIN" --redirect --non-interactive >/dev/null 2>&1 || true
else
  nginx -t >/dev/null 2>&1 && systemctl reload nginx
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect >/dev/null 2>&1 && log "HTTPS: сертификат выпущен" || fail "не удалось выпустить сертификат"
fi
nginx -t >/dev/null 2>&1 && systemctl reload nginx || fail "nginx: ошибка конфигурации"

# --- health ---
ok=""
for i in $(seq 1 30); do
  if curl -fsS "https://$DOMAIN/api/health" >/dev/null 2>&1; then ok=1; break; fi; sleep 2
done
[ -n "$ok" ] && log "Сайт: https://$DOMAIN — отвечает" || fail "сайт не отвечает (journalctl -u nova-api)"
curl -fsS -D - -o /dev/null "https://$DOMAIN/" | grep -qi "cache-control: no-cache" && log "Сброс кэша: index.html не кэшируется, файлы с хешем" || fail "заголовки кэша"
systemctl is-active --quiet nova-worker && log "Воркер: работает" || fail "воркер не запустился"

# --- telegram ---
TOKEN=$(getv BOT_TOKEN); WH=$(getv WEBHOOK_SECRET)
r=$(curl -fsS "https://api.telegram.org/bot$TOKEN/setWebhook" -d "url=https://$DOMAIN/api/tg/webhook" -d "secret_token=$WH" \
     -d 'allowed_updates=["message","my_chat_member","pre_checkout_query"]' -d "drop_pending_updates=false" || true)
echo "$r" | grep -q '"ok":true' && log "Бот: вебхук подключён" || fail "вебхук бота: $r"
curl -fsS "https://api.telegram.org/bot$TOKEN/setChatMenuButton" -H 'Content-Type: application/json' \
  -d "{\"menu_button\":{\"type\":\"web_app\",\"text\":\"NOVA\",\"web_app\":{\"url\":\"https://$DOMAIN/\"}}}" | grep -q '"ok":true' && log "Бот: кнопка меню открывает приложение" || fail "кнопка меню бота"
curl -fsS "https://api.telegram.org/bot$TOKEN/setMyDescription" --data-urlencode "description=NOVA — ИИ-агент: голос, картинки и логотипы, видео, музыка и озвучка. Нажмите «Старт»." >/dev/null || true

# --- russian check: on first install or when asked (RUCHECK=1) ---
if [ "${RUCHECK:-0}" = "1" ] || [ ! -f "$APP/.rucheck-done" ]; then
  touch "$APP/.rucheck-done"
  timeout 600 "$APP/venv/bin/python" tools/russian_check.py /tmp/russian.md >/dev/null 2>&1 && log "Проверка русского: готова, см. russian.md" || log "Проверка русского: не завершилась"
fi

# --- live check of paid services (one test picture on the first run of stage 2) ---
IMG=""; [ -f "$APP/.imgcheck3-done" ] || { IMG="--image"; touch "$APP/.imgcheck3-done"; }
timeout 300 "$APP/venv/bin/python" tools/services_check.py /tmp/services.md $IMG >/dev/null 2>&1 && log "Сервисы: проверены, см. services.md" || log "Сервисы: проверка не завершилась"

echo >> "$REPORT"; log "Статус: $STATUS"

# --- report to git (branch reports) ---
R=/opt/nova-reports
URL=$(git -C "$APP" remote get-url origin)
if [ ! -d "$R/.git" ]; then
  if git ls-remote --exit-code --heads "$URL" reports >/dev/null 2>&1; then git clone -q -b reports "$URL" "$R"
  else mkdir -p "$R" && git -C "$R" init -q -b reports && git -C "$R" remote add origin "$URL"; fi
fi
git -C "$R" fetch -q origin reports 2>/dev/null && git -C "$R" reset -q --hard origin/reports 2>/dev/null || true
cp "$REPORT" "$R/install.md"; [ -f /tmp/russian.md ] && cp /tmp/russian.md "$R/russian.md"; [ -f /tmp/services.md ] && cp /tmp/services.md "$R/services.md"
journalctl -u nova-api -n 200 --no-pager > "$R/api.log" 2>/dev/null || true
journalctl -u nova-worker -n 200 --no-pager > "$R/worker.log" 2>/dev/null || true
git -C "$R" add -A && git -C "$R" -c user.email=server@nova -c user.name=NOVA-server commit -qm "install $(date -u +%F_%H%M) $STATUS" >/dev/null 2>&1 || true
git -C "$R" push -q origin HEAD:refs/heads/reports 2>/dev/null && echo "Отчёт отправлен в git" || echo "Отчёт: не удалось отправить"
cat "$REPORT"
