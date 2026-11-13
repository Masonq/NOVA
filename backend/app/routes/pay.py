from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import payments as P
from ..pricing import refresh as refresh_prices
from ..config import get_settings
from ..db import get_db
from ..models import Payment, User, now
from ..security import current_user

router = APIRouter(prefix="/api/pay", tags=["pay"])


class BuyIn(BaseModel):
    pack: str


def out(p: Payment) -> dict:
    return {"id": p.id, "status": p.status, "method": p.method, "credits": p.credits, "amount": p.amount, "currency": p.currency}


@router.get("/packs")
async def packs(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await refresh_prices(db)
    methods = ["stars"] + (["crypto"] if get_settings().crypto_pay_token else [])
    return {"packs": [{**p, "total": P.total(p)} for p in P.PACKS], "methods": methods, "balance": u.balance}


async def _recent(db, u, method) -> int:
    rows = (await db.execute(select(Payment.id).where(Payment.user_id == u.id, Payment.method == method,
                                                       Payment.created_at > now() - timedelta(minutes=10)))).all()
    return len(rows)


@router.post("/stars")
async def buy_stars(body: BuyIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await refresh_prices(db)
    pack = P.pack_by_id(body.pack)
    if not pack:
        raise HTTPException(404, "Нет такого пакета")
    if await _recent(db, u, "stars") >= 10:
        raise HTTPException(429, "Слишком много попыток — подождите пару минут")
    try:
        p, link = await P.stars_invoice(db, u, pack)
    except Exception:
        raise HTTPException(503, "Telegram не создал счёт, попробуйте ещё раз")
    return {"payment": out(p), "link": link}


@router.post("/crypto")
async def buy_crypto(body: BuyIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await refresh_prices(db)
    pack = P.pack_by_id(body.pack)
    if not pack:
        raise HTTPException(404, "Нет такого пакета")
    if not get_settings().crypto_pay_token:
        raise HTTPException(503, "Оплата криптой пока не подключена")
    if await _recent(db, u, "crypto") >= 10:
        raise HTTPException(429, "Слишком много попыток — подождите пару минут")
    try:
        p, link = await P.crypto_invoice(db, u, pack)
    except Exception:
        raise HTTPException(503, "Не удалось создать счёт в @CryptoBot, попробуйте ещё раз")
    return {"payment": out(p), "link": link}


@router.get("/{pid}")
async def status(pid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    p = await db.get(Payment, pid)
    if not p or p.user_id != u.id:
        raise HTTPException(404, "Платёж не найден")
    if p.method == "crypto" and p.status == "pending":
        try:
            await P.crypto_sync(db, [p])
        except Exception:
            pass
        await db.refresh(p)
    await db.refresh(u)
    return {**out(p), "balance": u.balance}
