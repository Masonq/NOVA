import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

import jwt
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_db
from .models import User, now

INIT_DATA_MAX_AGE = 24 * 3600
TOKEN_TTL = 60 * 24 * 3600


def verify_init_data(init_data: str, bot_token: str, max_age: int = INIT_DATA_MAX_AGE) -> dict:
    """Telegram WebApp initData check (https://core.telegram.org/bots/webapps#validating-data)."""
    if not init_data or not bot_token:
        raise ValueError("empty")
    pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    received = pairs.pop("hash", None)
    if not received:
        raise ValueError("no hash")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received):
        raise ValueError("bad hash")
    if time.time() - int(pairs.get("auth_date", "0")) > max_age:
        raise ValueError("expired")
    user = json.loads(pairs.get("user", "{}"))
    if not user.get("id"):
        raise ValueError("no user")
    user["_start_param"] = pairs.get("start_param") or ""   # e.g. ref_12 when opened by a friend's link
    return user


def issue_token(user_id: int) -> str:
    s = get_settings()
    return jwt.encode({"uid": user_id, "exp": int(time.time()) + TOKEN_TTL}, s.jwt_secret, algorithm="HS256")


def read_token(token: str) -> int:
    s = get_settings()
    data = jwt.decode(token, s.jwt_secret, algorithms=["HS256"])
    return int(data["uid"])


async def upsert_tg_user(db: AsyncSession, tg: dict, ref: str | None = None) -> User:
    """Create or refresh a user from Telegram data. New users get the welcome pack once."""
    from .credits import grant
    s = get_settings()
    u = (await db.execute(select(User).where(User.tg_id == int(tg["id"])))).scalar_one_or_none()
    if u is None:
        u = User(tg_id=int(tg["id"]), first_name=(tg.get("first_name") or "")[:128], username=(tg.get("username") or "")[:64])
        db.add(u)
        await db.flush()
    else:
        u.first_name = (tg.get("first_name") or u.first_name)[:128]
        u.username = (tg.get("username") or u.username)[:64]
    u.last_seen = now()
    if not u.welcome_given:
        u.welcome_given = True
        from .pricing import PRICE, refresh
        await refresh(db)
        await grant(db, u, int(PRICE["welcome"]), "welcome", "Приветственный пакет")
        rid = int(ref[4:]) if ref and ref.startswith("ref_") and ref[4:].isdigit() else None
        if rid and rid != u.id and await db.get(User, rid) is not None:
            u.referrer_id = rid
            if PRICE.get("ref_friend"):
                await grant(db, u, int(PRICE["ref_friend"]), "promo", "Бонус за приглашение от друга")
    await db.commit()
    await db.refresh(u)
    return u


async def current_user(authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Нужен вход")
    try:
        uid = read_token(authorization[7:])
    except Exception:
        raise HTTPException(401, "Сессия истекла, войдите снова")
    u = await db.get(User, uid)
    if u is None:
        raise HTTPException(401, "Нужен вход")
    if u.blocked:
        raise HTTPException(403, "Аккаунт заблокирован")
    return u


def is_admin(u: User) -> bool:
    ids = {x.strip() for x in get_settings().admin_tg_ids.split(",") if x.strip()}
    return str(u.tg_id) in ids


async def admin_user(u: User = Depends(current_user)) -> User:
    if not is_admin(u):
        raise HTTPException(404, "Не найдено")
    return u
