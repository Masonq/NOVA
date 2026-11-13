from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import Job, Ledger, Memory, User
from ..security import current_user
from ..storage import remove_job_files

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("")
async def me(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    jobs = (await db.execute(select(func.count()).select_from(Job).where(Job.user_id == u.id))).scalar_one()
    return {"id": u.id, "name": u.first_name, "username": u.username, "balance": u.balance,
            "jobs": jobs, "keep_days": get_settings().keep_days, "since": u.created_at.isoformat()}


@router.get("/ledger")
async def ledger(limit: int = 50, before: int | None = None, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    q = select(Ledger).where(Ledger.user_id == u.id)
    if before:
        q = q.where(Ledger.id < before)
    rows = (await db.execute(q.order_by(Ledger.id.desc()).limit(min(limit, 100)))).scalars().all()
    return [{"id": r.id, "delta": r.delta, "balance": r.balance_after, "kind": r.kind, "title": r.title,
             "at": r.created_at.isoformat()} for r in rows]


@router.get("/memory")
async def memory(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Memory).where(Memory.user_id == u.id).order_by(Memory.id.desc()))).scalars().all()
    return [{"id": m.id, "text": m.text, "at": m.created_at.isoformat()} for m in rows]


@router.delete("/memory/{mid}")
async def forget_one(mid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    r = await db.execute(delete(Memory).where(Memory.id == mid, Memory.user_id == u.id))
    await db.commit()
    if not r.rowcount:
        raise HTTPException(404, "Уже удалено")
    return {"ok": True}


@router.delete("/memory")
async def forget_all(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(Memory).where(Memory.user_id == u.id))
    await db.commit()
    return {"ok": True}


@router.delete("")
async def delete_account(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Removes the user, their files, chat, memory and history."""
    jobs = (await db.execute(select(Job).where(Job.user_id == u.id))).scalars().all()
    for j in jobs:
        remove_job_files(j)
    await db.execute(delete(User).where(User.id == u.id))
    await db.commit()
    return {"ok": True}
