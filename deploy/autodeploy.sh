#!/usr/bin/env bash
# NOVA autodeploy: runs every minute from a systemd timer. When main has a new commit, it is installed once.
# A failed install is not retried for the same commit; the admin gets a message in Telegram either way.
set -u
{
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
# what changed, in plain Russian: the «Что нового:» list of every new commit (the subject when a commit has none)
if [ -n "$LAST" ] && git -C "$APP" cat-file -e "$LAST^{commit}" 2>/dev/null; then RANGE="$LAST..$NEW"; else RANGE="-1 $NEW"; fi
NOTES=$(git -C "$APP" log --reverse --format='%B%x1e' $RANGE | awk 'BEGIN { RS = "\036" }
  { n = split($0, L, "\n"); on = 0; got = 0; subj = ""
    for (i = 1; i <= n; i++) { l = L[i]
      if (subj == "" && l != "") subj = l
      if (l ~ /^Что нового:/) { on = 1; continue }
      if (on && l ~ /^- /) { print "• " substr(l, 3); got = 1 }
      else if (on && got && (l == "" || l ~ /^[A-Za-z-]+: /)) on = 0 }
    if (!got && subj != "") print "• " subj }' | head -c 3500)
if [ $RC -eq 0 ] && echo "$OUT" | grep -q "Статус: ok"; then T=$(printf '✅ NOVA обновлена\n\n%s' "$NOTES"); else T=$(printf '❌ Обновление NOVA не прошло — отчёт в git\n\n%s' "$NOTES"); fi
if [ -n "$TOKEN" ] && [ -n "$ADM" ]; then
  for id in ${ADM//,/ }; do curl -fsS -m 15 "https://api.telegram.org/bot$TOKEN/sendMessage" --data-urlencode "chat_id=$id" --data-urlencode "text=$T" >/dev/null 2>&1 || true; done
fi
exit 0
}
