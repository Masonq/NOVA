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


async def refund(db: AsyncSession, user: User, amount: int, title: str, job_id: int | None = None) -> int:
    if amount <= 0:
        return user.balance
    return await grant(db, user, amount, "refund", title, job_id)
