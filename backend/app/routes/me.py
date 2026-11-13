from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import Job, Ledger, Memory, User, now
from ..security import current_user, is_admin
from ..storage import remove_job_files

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("")
async def me(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    jobs = (await db.execute(select(func.count()).select_from(Job).where(Job.user_id == u.id))).scalar_one()
    # has the user ever spent credits (works can be deleted, the history stays): «new» texts are for those who haven't
    spent = (await db.execute(select(Ledger.id).where(Ledger.user_id == u.id, Ledger.delta < 0).limit(1))).first() is not None
    return {"id": u.id, "name": u.first_name, "username": u.username, "balance": u.balance,
            "jobs": jobs, "spent": spent, "keep_days": get_settings().keep_days, "since": u.created_at.isoformat(),
            "is_admin": is_admin(u)}


@router.get("/config")
async def config(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from ..pricing import PRICE, refresh
    await refresh(db)
    return {"price": PRICE}


class PromoIn(BaseModel):
    code: str


@router.post("/promo")
async def promo(body: PromoIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from ..credits import grant
    from ..models import PromoCode, PromoUse
    code = body.code.strip().upper()
    pc = (await db.execute(select(PromoCode).where(PromoCode.code == code).with_for_update())).scalar_one_or_none()
    if not pc or not pc.active or (pc.expires_at and pc.expires_at < now()):
        raise HTTPException(404, "Такого промокода нет или он закончился")
    if (await db.execute(select(PromoUse.id).where(PromoUse.promo_id == pc.id, PromoUse.user_id == u.id))).first():
        raise HTTPException(409, "Вы уже активировали этот промокод")
    if pc.used >= pc.max_uses:
        raise HTTPException(410, "Промокод уже использовали максимальное число раз")
    pc.used += 1
    db.add(PromoUse(promo_id=pc.id, user_id=u.id))
    await grant(db, u, pc.credits, "promo", f"Промокод {pc.code}")
    await db.commit()
    return {"credits": pc.credits, "balance": u.balance}


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



@router.get("/referral")
async def referral(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from ..pricing import PRICE, refresh
    await refresh(db)
    s = get_settings()
    invited = (await db.execute(select(func.count(User.id)).where(User.referrer_id == u.id))).scalar_one()
    paid = (await db.execute(select(func.count(User.id)).where(User.referrer_id == u.id, User.ref_rewarded.is_(True)))).scalar_one()
    return {"link": f"https://t.me/{s.bot_username}?start=ref_{u.id}", "invited": invited, "paid": paid,
            "earned": paid * int(PRICE.get("ref_bonus", 0)), "friend_bonus": int(PRICE.get("ref_friend", 0)), "bonus": int(PRICE.get("ref_bonus", 0))}
