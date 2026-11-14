#!/bin/bash
# Who spends the money: our own records of model spend (costs table) next to what OpenRouter and Kie say about the key.
# Usage: bash tools/spend.sh <out.md>     (read-only, free)
OUT=${1:-/tmp/spend.md}; APP=/opt/nova
getv(){ { grep "^$1=" "$APP/.env" 2>/dev/null || true; } | head -1 | cut -d= -f2-; }
OR=$(getv OPENROUTER_KEY); KIE=$(getv KIE_KEY)
q(){ sudo -u postgres psql -d nova -P pager=off -c "$1" 2>&1; }
{
echo "# Расходы — расследование $(date -u +'%F %H:%M UTC')"; echo
echo "## OpenRouter: что говорит сам OpenRouter"
echo '```'
echo "Ключ NOVA (/key):"; curl -sS -m 20 https://openrouter.ai/api/v1/key -H "Authorization: Bearer $OR" | python3 -c "import sys,json; d=json.load(sys.stdin).get('data',{}); [print(f'  {k}: {d.get(k)}') for k in ('label','usage','usage_daily','usage_weekly','usage_monthly','limit','limit_remaining','is_free_tier')]" 2>&1
echo "Весь аккаунт (/credits):"; curl -sS -m 20 https://openrouter.ai/api/v1/credits -H "Authorization: Bearer $OR" | python3 -c "import sys,json; d=json.load(sys.stdin); d=d.get('data',d); print('  ', d)" 2>&1
echo "Активность по дням и моделям (/activity, последние дни):"; curl -sS -m 30 https://openrouter.ai/api/v1/activity -H "Authorization: Bearer $OR" | python3 -c "
import sys,json
d=json.load(sys.stdin)
rows=d.get('data') if isinstance(d,dict) else None
if not rows: print('  ', str(d)[:300]); sys.exit()
rows=sorted(rows,key=lambda r:(r.get('date',''),-float(r.get('usage',0) or 0)),reverse=True)
for r in rows[:60]: print('  ', r.get('date','')[:10], f\"\${float(r.get('usage',0) or 0):.4f}\", r.get('model',''), 'запросов', r.get('requests',''), r.get('provider_name',''))
" 2>&1
echo '```'; echo
echo "## Kie"; echo '```'
curl -sS -m 20 --ipv4 https://api.kie.ai/api/v1/chat/credit -H "Authorization: Bearer $KIE" 2>&1 | head -c 300; echo
echo '```'; echo
echo "## Наши записи расходов (таблица costs) — по дням"; echo '```'
q "SELECT to_char(created_at,'MM-DD') d, provider, round(sum(usd)::numeric,4) usd, count(*) n FROM costs WHERE created_at > now()-interval '10 days' GROUP BY 1,2 ORDER BY 1 DESC,2"
echo '```'; echo "## За 3 дня: по видам и пометкам"; echo '```'
q "SELECT provider, kind, left(note,50) note, round(sum(usd)::numeric,4) usd, count(*) n FROM costs WHERE created_at > now()-interval '3 days' GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 40"
echo '```'; echo "## За 3 дня: по пользователям"; echo '```'
q "SELECT c.user_id, u.tg_id, left(coalesce(u.first_name,''),20) name, round(sum(c.usd)::numeric,4) usd, count(*) n FROM costs c LEFT JOIN users u ON u.id=c.user_id WHERE c.created_at > now()-interval '3 days' GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 20"
echo '```'; echo "## Работы за 3 дня по видам и статусам"; echo '```'
q "SELECT kind, status, count(*) n, sum(cost) credits FROM jobs WHERE created_at > now()-interval '3 days' GROUP BY 1,2 ORDER BY 1,2"
echo '```'; echo "## Последние 30 записей расходов"; echo '```'
q "SELECT to_char(created_at,'MM-DD HH24:MI') t, provider, kind, user_id, job_id, round(usd::numeric,5) usd, left(note,45) note FROM costs ORDER BY id DESC LIMIT 30"
echo '```'
} > "$OUT"
