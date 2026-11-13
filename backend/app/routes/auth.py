import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
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


def device_name(ua: str) -> str:
    ua = ua or ""
    browser = next((n for k, n in (("Edg/", "Edge"), ("OPR/", "Opera"), ("YaBrowser", "Яндекс Браузер"), ("Firefox/", "Firefox"),
                                   ("Chrome/", "Chrome"), ("Safari/", "Safari")) if k in ua), "Браузер")
    osn = next((n for k, n in (("Windows", "Windows"), ("Mac OS X", "macOS"), ("Android", "Android"), ("iPhone", "iPhone"),
                               ("iPad", "iPad"), ("Linux", "Linux")) if k in ua), "")
    return f"{browser} · {osn}" if osn else browser


def client_ip(request: Request) -> str:
    return (request.headers.get("x-real-ip") or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else ""))[:64]


@router.post("/code")
async def new_login_code(request: Request, db: AsyncSession = Depends(get_db)):
    """Site / PWA: open the bot with this code (or scan its QR in the mini app), the site picks the session up."""
    code = secrets.token_urlsafe(18)
    db.add(LoginCode(code=code, device=device_name(request.headers.get("user-agent", "")), ip=client_ip(request)))
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



def _code_from(text: str) -> str:
    """The QR holds the bot link …?start=login_<code>; accept the bare code as well."""
    import re
    m = re.search(r"login_([A-Za-z0-9_-]{16,40})", text or "")
    return m.group(1) if m else (text if re.fullmatch(r"[A-Za-z0-9_-]{16,40}", text or "") else "")


class ScanIn(BaseModel):
    qr: str


@router.post("/scan")
async def scan_info(body: ScanIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Step 1 in the mini app: what is asking to sign in — shown to the user before they confirm."""
    code = _code_from(body.qr.strip())
    lc = await db.get(LoginCode, code) if code else None
    if lc is None or lc.used or lc.user_id or now() - lc.created_at > CODE_TTL:
        raise HTTPException(410, "Этот QR-код устарел — обновите страницу на компьютере")
    mins = int((now() - lc.created_at).total_seconds() // 60)
    return {"code": code, "device": lc.device or "Браузер", "ip": lc.ip, "ago": "только что" if mins < 1 else f"{mins} мин назад"}


class ConfirmIn(BaseModel):
    code: str


@router.post("/scan/confirm")
async def scan_confirm(body: ConfirmIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    """Step 2: the user confirmed — the computer that shows this QR signs in as this user (once)."""
    lc = await db.get(LoginCode, _code_from(body.code))
    if lc is None or lc.used or lc.user_id or now() - lc.created_at > CODE_TTL:
        raise HTTPException(410, "Этот QR-код устарел — обновите страницу на компьютере")
    lc.user_id = u.id
    await db.commit()
    return {"ok": True}
