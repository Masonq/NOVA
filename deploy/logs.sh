#!/bin/bash
# Sends fresh logs and the latest jobs (with error texts) to the reports branch. No reinstall, no restart.
APP=/opt/nova; R=/opt/nova-reports
URL=$(git -C "$APP" remote get-url origin)
[ -d "$R/.git" ] || { git clone -q -b reports "$URL" "$R" 2>/dev/null || { mkdir -p "$R"; git -C "$R" init -q -b reports; git -C "$R" remote add origin "$URL"; }; }
git -C "$R" fetch -q origin reports 2>/dev/null && git -C "$R" reset -q --hard origin/reports 2>/dev/null
journalctl -u nova-api -n 400 --no-pager > "$R/api.log" 2>/dev/null
journalctl -u nova-worker -n 400 --no-pager > "$R/worker.log" 2>/dev/null
Q="SELECT id, kind, status, stage, progress, cost, to_char(created_at,'DD.MM HH24:MI') AS at, left(prompt,60) AS prompt, params::text AS params, left(error,400) AS error FROM jobs ORDER BY id DESC LIMIT 15"
{ echo "# Последние работы $(date -u +'%F %H:%M UTC')"; echo; sudo -u postgres psql -d nova -P pager=off -c "$Q"; } > "$R/jobs.md" 2>&1
bash "$APP/tools/spend.sh" "$R/spend.md" 2>/dev/null || true
git -C "$R" add -A && git -C "$R" -c user.email=server@nova -c user.name=NOVA-server commit -qm "logs $(date -u +%F_%H%M)" >/dev/null 2>&1
git -C "$R" push -q origin HEAD:refs/heads/reports 2>/dev/null && echo "Логи отправлены в git" || echo "Не удалось отправить логи"
