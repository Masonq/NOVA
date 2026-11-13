#!/usr/bin/env bash
# NOVA autodeploy: runs every minute from a systemd timer. When main has a new commit, it is installed once.
# A failed install is not retried for the same commit; the admin gets a message in Telegram either way.
set -u
APP=/opt/nova; STATE=$APP/.autodeploy-sha; LOG=/var/log/nova-autodeploy.log
exec 9>/run/nova-autodeploy.lock
flock -n 9 || exit 0                                   # an install is already running
git -C "$APP" fetch -q origin main 2>>"$LOG" || exit 0
NEW=$(git -C "$APP" rev-parse origin/main)
LAST=$(cat "$STATE" 2>/dev/null || true)
[ "$NEW" = "$LAST" ] && exit 0                         # nothing new (or this commit was already attempted)
echo "$NEW" > "$STATE"
git -C "$APP" reset -q --hard origin/main
echo "=== $(date -u '+%F %T') autodeploy $(git -C "$APP" log -1 --format='%h %s')" >> "$LOG"
OUT=$(AUTODEPLOY=1 bash "$APP/deploy/install.sh" 2>&1); RC=$?
echo "$OUT" >> "$LOG"
getv(){ { grep "^$1=" "$APP/.env" 2>/dev/null || true; } | head -1 | cut -d= -f2-; }
TOKEN=$(getv BOT_TOKEN); ADM=$(getv ADMIN_TG_IDS)
MSG=$(git -C "$APP" log -1 --format='%s' | cut -c1-300)
if [ $RC -eq 0 ] && echo "$OUT" | grep -q "Статус: ok"; then T="✅ NOVA обновлена: $MSG"; else T="❌ Обновление NOVA не прошло: $MSG — отчёт в git"; fi
if [ -n "$TOKEN" ] && [ -n "$ADM" ]; then
  for id in ${ADM//,/ }; do curl -fsS -m 15 "https://api.telegram.org/bot$TOKEN/sendMessage" --data-urlencode "chat_id=$id" --data-urlencode "text=$T" >/dev/null 2>&1 || true; done
fi
