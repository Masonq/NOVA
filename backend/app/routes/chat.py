import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import Session, get_db
from ..ai import AIError, stream_text
from ..models import ChatMessage, Memory, User, now
from ..security import current_user

router = APIRouter(prefix="/api/chat", tags=["chat"])
HISTORY = 20

SYSTEM = """Ты — NOVA, ИИ-агент в приложении NOVA. Отвечай по-русски, коротко и по делу, дружелюбно, без эмодзи.
Ты умеешь создавать изображения и логотипы, видео, музыку и озвучку — пользователь запускает их кнопками на главном экране,
а скоро сможет и прямо из разговора. Если просят что-то сгенерировать, а модуль ещё не подключён, честно скажи, что эта функция скоро появится.
Не выдумывай факты; если не знаешь — скажи об этом."""


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def _sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


@router.get("")
async def history(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(ChatMessage).where(ChatMessage.user_id == u.id)
                             .order_by(ChatMessage.id.desc()).limit(100))).scalars().all()
    return [{"id": m.id, "role": m.role, "text": m.text, "at": m.created_at.isoformat()} for m in reversed(rows)]


@router.delete("")
async def clear(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(ChatMessage).where(ChatMessage.user_id == u.id))
    await db.commit()
    return {"ok": True}


@router.post("")
async def send(body: ChatIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    s = get_settings()
    today = (await db.execute(select(func.count()).select_from(ChatMessage).where(
        ChatMessage.user_id == u.id, ChatMessage.role == "user", ChatMessage.created_at > now() - timedelta(days=1)))).scalar_one()
    if today >= s.chat_daily_limit:
        raise HTTPException(429, "Лимит сообщений на сегодня исчерпан, продолжим завтра")
    text = body.text.strip()
    db.add(ChatMessage(user_id=u.id, role="user", text=text))
    await db.commit()
    rows = (await db.execute(select(ChatMessage).where(ChatMessage.user_id == u.id)
                             .order_by(ChatMessage.id.desc()).limit(HISTORY))).scalars().all()
    contents = [{"role": "assistant" if m.role == "model" else "user", "content": m.text} for m in reversed(rows)]
    facts = (await db.execute(select(Memory.text).where(Memory.user_id == u.id).order_by(Memory.id.desc()).limit(30))).scalars().all()
    system = SYSTEM + (f"\nПользователя зовут {u.first_name}." if u.first_name else "")
    if facts:
        system += "\nЧто ты знаешь о пользователе:\n- " + "\n- ".join(facts)
    uid = u.id

    async def gen():
        out = []
        try:
            async for chunk in stream_text(s.chat_models, contents, system):
                out.append(chunk)
                yield _sse({"t": chunk})
        except AIError:
            if not out:
                yield _sse({"error": "Модель сейчас перегружена, попробуйте ещё раз через минуту"})
                return
        reply = "".join(out).strip()
        if reply:
            async with Session() as s2:
                s2.add(ChatMessage(user_id=uid, role="model", text=reply))
                await s2.commit()
        yield _sse({"done": True})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
