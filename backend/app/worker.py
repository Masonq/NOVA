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
    await init_db()


class WorkerSettings:
    functions: list = []
    cron_jobs = [cron(cleanup_expired, minute={7, 37}), cron(remind_expiring, hour={9}, minute={0})]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    max_jobs = 8
