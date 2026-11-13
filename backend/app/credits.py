from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Ledger, User


async def _locked(db: AsyncSession, user: User) -> User:
    return (await db.execute(select(User).where(User.id == user.id).with_for_update())).scalar_one()


async def grant(db: AsyncSession, user: User, amount: int, kind: str, title: str, job_id: int | None = None) -> int:
    """Add credits. Caller commits."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    u = await _locked(db, user) if user.id else user
    u.balance += amount
    db.add(Ledger(user_id=u.id, delta=amount, balance_after=u.balance, kind=kind, title=title[:200], job_id=job_id))
    return u.balance


async def charge(db: AsyncSession, user: User, amount: int, title: str, job_id: int | None = None) -> int:
    """Take credits atomically; refuses when the balance is short. Caller commits."""
    if amount <= 0:
        return user.balance
    u = await _locked(db, user)
    if u.balance < amount:
        raise HTTPException(402, f"Не хватает кредитов: нужно {amount}, на балансе {u.balance}")
    u.balance -= amount
    db.add(Ledger(user_id=u.id, delta=-amount, balance_after=u.balance, kind="charge", title=title[:200], job_id=job_id))
    return u.balance


async def charge_daily(db: AsyncSession, user: User, amount: int, label: str) -> int:
    """Small repeated charges (text chat) are folded into one ledger line per day: «label: N сообщений»."""
    import re
    from datetime import timedelta
    from sqlalchemy import select
    from .models import now
    u = await _locked(db, user)
    if u.balance < amount:
        raise HTTPException(402, f"Не хватает кредитов: нужно {amount}, на балансе {u.balance}")
    u.balance -= amount
    day0 = now().replace(hour=0, minute=0, second=0, microsecond=0)
    row = (await db.execute(select(Ledger).where(Ledger.user_id == u.id, Ledger.kind == "charge", Ledger.title.like(f"{label}:%"),
                                                 Ledger.created_at >= day0).order_by(Ledger.id.desc()).limit(1).with_for_update())).scalar_one_or_none()
    if row:
        n = int((re.search(r"(\d+)", row.title) or [0, 0])[1]) + 1
        row.delta -= amount
        row.balance_after = u.balance
        row.title = f"{label}: {n} {plural(n)}"
    else:
        db.add(Ledger(user_id=u.id, delta=-amount, balance_after=u.balance, kind="charge", title=f"{label}: 1 сообщение"))
    return u.balance


def plural(n: int) -> str:
    a, b = n % 10, n % 100
    return "сообщение" if a == 1 and b != 11 else "сообщения" if 2 <= a <= 4 and not 12 <= b <= 14 else "сообщений"


async def refund(db: AsyncSession, user: User, amount: int, title: str, job_id: int | None = None) -> int:
    if amount <= 0:
        return user.balance
    return await grant(db, user, amount, "refund", title, job_id)
