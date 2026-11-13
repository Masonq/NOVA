"""Background worker: generation queue (stage 2) and file lifecycle (30 days)."""
import logging
from datetime import timedelta

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select

from . import bot
from .config import get_settings
from .db import Session, init_db
from .models import Job, User, now
from .storage import remove_job_files
from .runner import run_job


async def send_broadcast(ctx, bid: int):
    """Sends a broadcast to everyone who can receive messages, ~20 messages per second, can be cancelled."""
    import asyncio
    from .models import Broadcast
    async with Session() as db:
        b = await db.get(Broadcast, bid)
        if not b or b.status != "queued":
            return
        b.status = "sending"; await db.commit()
        ids = (await db.execute(select(User.id, User.tg_id).where(User.can_message.is_(True), User.blocked.is_(False)).order_by(User.id))).all()
    markup = bot.open_app_markup(b.button) if b.button else None
    sent = failed = 0
    for i, (uid, tg_id) in enumerate(ids):
        if i % 50 == 0:
            async with Session() as db:
                x = await db.get(Broadcast, bid)
                if x.status == "cancelled":
                    return
                x.sent, x.failed = sent, failed; await db.commit()
        r = await bot.send(tg_id, b.text, markup)
        if r.get("ok"):
            sent += 1
        else:
            failed += 1
            if r.get("error_code") == 403:
                async with Session() as db:
                    u = await db.get(User, uid); u.can_message = False; await db.commit()
            elif r.get("error_code") == 429:
                await asyncio.sleep(int((r.get("parameters") or {}).get("retry_after", 3)))
        await asyncio.sleep(0.05)
    async with Session() as db:
        x = await db.get(Broadcast, bid)
        x.sent, x.failed = sent, failed
        if x.status != "cancelled":
            x.status = "done"
        x.finished_at = now(); await db.commit()
    log.info("broadcast %s: sent %s, failed %s", bid, sent, failed)


async def sync_crypto(ctx):
    """Pending crypto invoices of the last 2 hours: grant credits for the paid ones (no webhook needed)."""
    from datetime import timedelta
    from . import payments as P
    from .models import Payment, now
    if not get_settings().crypto_pay_token:
        return
    async with Session() as db:
        rows = (await db.execute(select(Payment).where(Payment.method == "crypto", Payment.status == "pending",
                                                       Payment.created_at > now() - timedelta(hours=2)))).scalars().all()
        if rows:
            try:
                await P.crypto_sync(db, list(rows))
            except Exception as e:
                log.warning("crypto sync: %s", e)

log = logging.getLogger("nova.worker")


async def cleanup_expired(ctx=None) -> int:
    """Delete files of jobs past their expiry; the row stays as 'expired' for the ledger history."""
    n = 0
    async with Session() as db:
        rows = (await db.execute(select(Job).where(Job.expires_at.is_not(None), Job.expires_at <= now(),
                                                    Job.status != "expired").limit(500))).scalars().all()
        for j in rows:
            remove_job_files(j)
            j.status, j.files = "expired", []
            n += 1
        await db.commit()
    if n:
        log.info("expired %s jobs", n)
    return n


def _plural(n: int) -> str:
    if n % 10 == 1 and n % 100 != 11:
        return "работа"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "работы"
    return "работ"


async def remind_expiring(ctx=None) -> int:
    """One message per user: N works will be deleted in remind_before_days days."""
    s = get_settings()
    horizon = now() + timedelta(days=s.remind_before_days)
    sent = 0
    async with Session() as db:
        rows = (await db.execute(select(Job).where(Job.status == "done", Job.reminded.is_(False),
                                                    Job.expires_at.is_not(None), Job.expires_at <= horizon))).scalars().all()
        by_user: dict[int, list[Job]] = {}
        for j in rows:
            by_user.setdefault(j.user_id, []).append(j)
        for uid, js in by_user.items():
            u = await db.get(User, uid)
            if u and u.can_message:
                n = len(js)
                await bot.send(u.tg_id, f"Через {s.remind_before_days} дня удалятся {n} {_plural(n)}. "
                                        "Если что-то нужно сохранить — скачайте в архиве.", bot.open_app_markup("Открыть архив", "#/archive"))
                sent += 1
            for j in js:
                j.reminded = True
        await db.commit()
    return sent


async def startup(ctx):
    """Pick up generations that were in progress when the worker stopped."""
    await init_db()
    from .queue import enqueue
    async with Session() as db:
        rows = (await db.execute(select(Job.id).where(Job.status.in_(("queued", "running"))))).scalars().all()
    for jid in rows:
        try:
            await enqueue(jid)
        except Exception as e:
            log.warning("re-enqueue %s: %s", jid, e)


class WorkerSettings:
    functions = [run_job, send_broadcast]
    job_timeout = 2400
    cron_jobs = [cron(cleanup_expired, minute={7, 37}), cron(remind_expiring, hour={9}, minute={0}),
                 cron(sync_crypto, second={20}, run_at_startup=False)]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 8
