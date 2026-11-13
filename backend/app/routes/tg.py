import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import bot
from ..config import get_settings
from ..db import get_db
from ..models import LoginCode, User, now
from ..security import upsert_tg_user

router = APIRouter(prefix="/api/tg", tags=["telegram"])
log = logging.getLogger("nova.tg")

HELLO = ("<b>Привет! Я NOVA</b> — ИИ-агент.\n\n"
         "Разговариваю голосом, создаю картинки и логотипы, видео, музыку и озвучку.\n"
         "Открой приложение кнопкой ниже — там уже ждут приветственные кредиты.")


@router.post("/webhook")
async def webhook(request: Request, x_telegram_bot_api_secret_token: str = Header(default=""),
                  db: AsyncSession = Depends(get_db)):
    if x_telegram_bot_api_secret_token != get_settings().webhook_secret:
        raise HTTPException(403)
    upd = await request.json()
    msg = upd.get("message") or {}
    frm = msg.get("from") or {}
    text = (msg.get("text") or "").strip()
    if upd.get("my_chat_member"):
        m = upd["my_chat_member"]
        u = (await db.execute(select(User).where(User.tg_id == m["from"]["id"]))).scalar_one_or_none()
        if u:
            u.can_message = m.get("new_chat_member", {}).get("status") not in ("kicked", "left")
            await db.commit()
        return {"ok": True}
    if not frm.get("id") or msg.get("chat", {}).get("type") != "private":
        return {"ok": True}
    u = await upsert_tg_user(db, frm)
    u.can_message = True
    if text.startswith("/start login_"):
        code = text.split("login_", 1)[1].strip()
        lc = await db.get(LoginCode, code)
        if lc and not lc.used and not lc.user_id and (now() - lc.created_at).total_seconds() < 600:
            lc.user_id = u.id
            await db.commit()
            await bot.send(frm["id"], "Готово, вход подтверждён. Вернитесь на сайт — он откроется сам.")
        else:
            await db.commit()
            await bot.send(frm["id"], "Эта ссылка для входа устарела. Обновите страницу сайта и нажмите «Войти» ещё раз.")
        return {"ok": True}
    await db.commit()
    await bot.send(frm["id"], HELLO, bot.open_app_markup())
    return {"ok": True}
