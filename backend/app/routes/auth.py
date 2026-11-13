import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import LoginCode, User, now
from ..security import current_user, issue_token, upsert_tg_user, verify_init_data

router = APIRouter(prefix="/api/auth", tags=["auth"])
CODE_TTL = timedelta(minutes=10)


class WebAppIn(BaseModel):
    initData: str


def _out(u: User) -> dict:
    return {"token": issue_token(u.id), "user": {"id": u.id, "name": u.first_name, "balance": u.balance}}


@router.post("/webapp")
async def webapp_login(body: WebAppIn, db: AsyncSession = Depends(get_db)):
    try:
        tg = verify_init_data(body.initData, get_settings().bot_token)
    except Exception:
        raise HTTPException(401, "Не удалось подтвердить вход через Telegram")
    u = await upsert_tg_user(db, tg, ref=tg.get("_start_param"))
    if u.blocked:
        raise HTTPException(403, "Аккаунт заблокирован")
    return _out(u)


@router.post("/code")
async def new_login_code(db: AsyncSession = Depends(get_db)):
    """Site / PWA: open the bot with this code, press Start, the site picks the session up."""
    code = secrets.token_urlsafe(18)
    db.add(LoginCode(code=code))
    await db.commit()
    s = get_settings()
    return {"code": code, "link": f"https://t.me/{s.bot_username}?start=login_{code}", "ttl": int(CODE_TTL.total_seconds())}


@router.get("/code/{code}")
async def poll_login_code(code: str, db: AsyncSession = Depends(get_db)):
    lc = await db.get(LoginCode, code)
    if lc is None or lc.used or now() - lc.created_at > CODE_TTL:
        raise HTTPException(410, "Ссылка для входа устарела, получите новую")
    if not lc.user_id:
        return {"status": "waiting"}
    u = await db.get(User, lc.user_id)
    lc.used = True
    await db.commit()
    if u is None or u.blocked:
        raise HTTPException(403, "Вход недоступен")
    return {"status": "ok", **_out(u)}



@router.post("/handoff")
async def handoff(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """From the Telegram mini app to the website already signed in: a one-time link that lives 10 minutes."""
    code = secrets.token_urlsafe(18)
    db.add(LoginCode(code=code, user_id=u.id))
    await db.commit()
    return {"url": f"{get_settings().public_url}/?handoff={code}#/profile?topup=card"}
