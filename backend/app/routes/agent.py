"""Voice agent NOVA. One turn: the user's speech (WAV) or text in, a stream of events out:
heard (what was understood), step (work in progress), text (answer as it is written), audio (spoken sentence),
confirm / job / cards (actions), done. Generations need an explicit "yes"."""
import asyncio
import base64
import io
import json
import math
import re
import secrets
import time
import wave
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import ai
from ..config import get_settings
from ..credits import charge
from ..db import Session, get_db
from ..models import ChatMessage, Job, Memory, User
from ..pricing import PRICE, cost as price_of, refresh as refresh_prices
from ..security import current_user
from .jobs import job_out, start_job

router = APIRouter(prefix="/api/agent", tags=["agent"])
MODEL = "google/gemini-3.8-flash"
HISTORY = 12
KINDS = {"image": "картинку", "video": "видео", "music": "трек", "tts": "озвучку"}

SYSTEM = """Ты — NOVA, голосовой ИИ-агент в приложении NOVA. Говоришь по-русски живо и тепло, как умный друг.
Твой ответ озвучивается голосом, поэтому:
- отвечай коротко: 1–3 предложения, первое — самое короткое; без списков, markdown, эмодзи и ссылок;
- числа и даты пиши так, как их естественно произнести.
Возможности (инструменты):
- create_media — создать картинку/логотип, видео, музыку или озвучку. Сначала вызови его — пользователь увидит цену;
  скажи цену одной фразой и спроси, запускать ли. Запускай только после явного согласия через confirm_pending.
- search_archive — найти работы пользователя (за последние 30 дней).
- web_search — свежие факты, новости, погода, цены.
- remember / forget — запомнить или забыть факт о пользователе, когда он просит или сообщает что-то важное о себе.
Не выдумывай факты. Если не знаешь — скажи и предложи поискать."""
HEARD_RULE = """Ответ начинай строго с [[точная расшифровка того, что сказал пользователь]], затем сразу свой ответ.
Если в аудио нет речи или она неразборчива — ответь [[]] и попроси повторить."""

TOOLS = [
    {"type": "function", "function": {"name": "create_media", "description": "Подготовить генерацию: показать цену и ждать согласия пользователя",
        "parameters": {"type": "object", "required": ["kind", "prompt"], "properties": {
            "kind": {"type": "string", "enum": ["image", "video", "music", "tts"]},
            "prompt": {"type": "string", "description": "Подробное описание на русском (для tts — точный текст для озвучки)"},
            "style": {"type": "string", "enum": ["Фото", "Арт", "Логотип", "3D", "Аниме"]},
            "aspect": {"type": "string", "enum": ["1:1", "3:4", "9:16", "16:9"]},
            "duration": {"type": "integer", "enum": [5, 10, 15]},
            "sound": {"type": "boolean"},
            "genre": {"type": "string"}, "instrumental": {"type": "boolean"}}}}},
    {"type": "function", "function": {"name": "confirm_pending", "description": "Пользователь ответил на вопрос о запуске подготовленной генерации",
        "parameters": {"type": "object", "required": ["yes"], "properties": {"yes": {"type": "boolean"}}}}},
    {"type": "function", "function": {"name": "search_archive", "description": "Найти работы пользователя по словам из описания",
        "parameters": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"},
            "kind": {"type": "string", "enum": ["image", "video", "music", "tts"]}}}}},
    {"type": "function", "function": {"name": "web_search", "description": "Поиск свежей информации в интернете",
        "parameters": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "remember", "description": "Запомнить факт о пользователе",
        "parameters": {"type": "object", "required": ["fact"], "properties": {"fact": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "forget", "description": "Забыть факт о пользователе",
        "parameters": {"type": "object", "required": ["about"], "properties": {"about": {"type": "string"}}}}},
]


# ---------- pending action (shared between API processes) ----------
class Pending:
    async def _r(self):
        from redis.asyncio import from_url
        return from_url(get_settings().redis_url, decode_responses=True)

    async def set(self, uid: int, data: dict):
        r = await self._r()
        await r.set(f"nova:agent:pending:{uid}", json.dumps(data, ensure_ascii=False), ex=600)
        await r.aclose()

    async def pop(self, uid: int) -> dict | None:
        r = await self._r()
        v = await r.getdel(f"nova:agent:pending:{uid}")
        await r.aclose()
        return json.loads(v) if v else None


pending = Pending()


def _sse(o: dict) -> str:
    return "data: " + json.dumps(o, ensure_ascii=False) + "\n\n"


def wav_seconds(raw: bytes) -> float:
    try:
        with wave.open(io.BytesIO(raw)) as w:
            return w.getnframes() / float(w.getframerate())
    except Exception:
        return 0.0


def audio_dir(uid: int) -> Path:
    d = Path(get_settings().storage_dir) / "agent" / str(uid)
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.wav"):
        if time.time() - f.stat().st_mtime > 3600:
            f.unlink(missing_ok=True)
    return d


SENT = re.compile(r"(.+?[.!?…]+)(\s+|$)", re.S)


def split_ready(buf: str, first: bool) -> tuple[list[str], str]:
    """Cuts finished sentences off the buffer. The first chunk may end at a comma to start speaking sooner."""
    out = []
    while True:
        m = SENT.match(buf)
        if m and len(m.group(1).strip()) >= 2 and (m.end() < len(buf) or buf.endswith((" ", "\n"))):
            out.append(m.group(1).strip()); buf = buf[m.end():]
            continue
        if first and not out and len(buf) > 60 and "," in buf[25:]:
            i = buf.index(",", 25) + 1
            out.append(buf[:i].strip()); buf = buf[i:].lstrip()
            continue
        return out, buf


class TurnIn(BaseModel):
    audio: str | None = Field(default=None, max_length=8_000_000)   # base64 WAV, up to ~45 s of 16 kHz speech
    text: str | None = Field(default=None, max_length=2000)


class SettingsIn(BaseModel):
    voice: str


@router.get("/settings")
async def get_settings_(u: User = Depends(current_user)):
    return {"voice": u.agent_voice, "voices": [{"id": k, "name": v} for k, v in ai.VOICES.items()], "per_min": PRICE["agent_min"]}


@router.put("/settings")
async def put_settings(body: SettingsIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if body.voice not in ai.VOICES:
        raise HTTPException(422, "Нет такого голоса")
    u.agent_voice = body.voice
    await db.commit()
    return {"voice": u.agent_voice}


@router.delete("/history")
async def clear(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await db.execute(delete(ChatMessage).where(ChatMessage.user_id == u.id, ChatMessage.channel == "agent"))
    await db.commit()
    return {"ok": True}


async def run_tool(name: str, args: dict, u: User, emit) -> str:
    """Executes a tool call; emits UI events; returns the text the model sees."""
    async with Session() as db:
        user = await db.get(User, u.id)
        if name == "create_media":
            kind = args.get("kind")
            if kind not in KINDS or len((args.get("prompt") or "").strip()) < 2:
                return "Не хватает описания — уточни у пользователя, что создать."
            params = {k: args[k] for k in ("style", "aspect", "duration", "sound", "genre", "instrumental") if k in args}
            if kind == "tts":
                params["voice"] = user.agent_voice
            price = price_of(kind, params, args["prompt"])
            await pending.set(u.id, {"kind": kind, "prompt": args["prompt"].strip(), "params": params, "cost": price})
            await emit({"type": "confirm", "kind": kind, "prompt": args["prompt"].strip(), "cost": price, "balance": user.balance})
            if price > user.balance:
                return f"Цена {price} кредитов, а на балансе {user.balance} — не хватает. Скажи об этом и предложи пополнить баланс в профиле."
            return f"Подготовлено: {KINDS[kind]}, цена {price} кредитов (на балансе {user.balance}). Назови цену и спроси, запускать ли."
        if name == "confirm_pending":
            p = await pending.pop(u.id)
            if not p:
                return "Нечего запускать: подготовленной генерации нет."
            if not args.get("yes"):
                await emit({"type": "confirm_cancel"})
                return "Отменено, кредиты не списаны."
            try:
                j = await start_job(db, user, p["kind"], p["prompt"], p["params"])
            except HTTPException as e:
                await emit({"type": "confirm_cancel"})
                return f"Не запустилось: {e.detail}"
            await emit({"type": "job", "job": job_out(j), "balance": user.balance})
            return f"Запущено: {KINDS[p['kind']]}. Списано {j.cost} кредитов. Скажи, что пришлёшь, когда будет готово."
        if name == "search_archive":
            words = [w for w in re.findall(r"\w{3,}", (args.get("query") or "").lower())][:5]
            q = select(Job).where(Job.user_id == u.id, Job.status == "done")
            if args.get("kind") in KINDS:
                q = q.where(Job.kind == args["kind"])
            if words:
                q = q.where(or_(*[Job.prompt.ilike(f"%{w[:-1] if len(w) > 4 else w}%") for w in words]))
            rows = (await db.execute(q.order_by(Job.id.desc()).limit(5))).scalars().all()
            if not rows:
                return "В архиве ничего не нашлось."
            await emit({"type": "cards", "jobs": [job_out(j) for j in rows]})
            return "Нашлось: " + "; ".join(f"{KINDS[j.kind]} «{j.prompt[:60]}»" for j in rows) + ". Карточки уже на экране."
        if name == "web_search":
            await emit({"type": "step", "text": "Ищу в интернете"})
            try:
                ans = await ai.web_answer(args.get("query") or "")
            except ai.AIError:
                ans = "Поиск сейчас недоступен."
            await emit({"type": "step", "text": "Ищу в интернете", "done": True})
            return ans
        if name == "remember":
            fact = (args.get("fact") or "").strip()[:300]
            if fact:
                db.add(Memory(user_id=u.id, text=fact)); await db.commit()
                await emit({"type": "memory", "text": fact})
            return "Запомнил."
        if name == "forget":
            about = (args.get("about") or "").strip()
            if about:
                await db.execute(delete(Memory).where(Memory.user_id == u.id, Memory.text.ilike(f"%{about[:40]}%")))
                await db.commit()
            return "Забыл."
    return "Неизвестный инструмент."


@router.post("/turn")
async def turn(body: TurnIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    if not body.audio and not (body.text or "").strip():
        raise HTTPException(422, "Пустой запрос")
    await refresh_prices(db)
    if u.balance < 1:
        raise HTTPException(402, "Кредиты закончились — пополните баланс, чтобы продолжить разговор")
    raw = b""
    if body.audio:
        try:
            raw = base64.b64decode(body.audio.split(",")[-1], validate=False)
        except Exception:
            raise HTTPException(422, "Не удалось прочитать звук")
        if wav_seconds(raw) < 0.3:
            raise HTTPException(422, "Слишком короткая запись")
    rows = (await db.execute(select(ChatMessage).where(ChatMessage.user_id == u.id, ChatMessage.channel == "agent")
                             .order_by(ChatMessage.id.desc()).limit(HISTORY))).scalars().all()
    facts = (await db.execute(select(Memory.text).where(Memory.user_id == u.id).order_by(Memory.id.desc()).limit(30))).scalars().all()
    system = SYSTEM + (f"\nПользователя зовут {u.first_name}." if u.first_name else "") + f"\nБаланс пользователя: {u.balance} кредитов."
    if facts:
        system += "\nЧто ты знаешь о пользователе:\n- " + "\n- ".join(facts)
    if raw:
        system += "\n" + HEARD_RULE
    msgs = [{"role": "system", "content": system}]
    msgs += [{"role": "assistant" if m.role == "model" else "user", "content": m.text} for m in reversed(rows)]
    if raw:
        msgs.append({"role": "user", "content": [{"type": "input_audio", "input_audio": {"data": base64.b64encode(raw).decode(), "format": "wav"}}]})
    else:
        msgs.append({"role": "user", "content": body.text.strip()})
    uid, voice, in_sec = u.id, u.agent_voice, wav_seconds(raw) if raw else 0.0
    s = get_settings()
    d = audio_dir(uid)

    async def gen():
        q: asyncio.Queue = asyncio.Queue()
        heard = None if raw else body.text.strip()
        answer: list[str] = []
        out_sec = 0.0
        tts_tasks: list[asyncio.Task] = []

        async def emit(o):
            await q.put(o)

        async def speak(seq: int, text: str):
            try:
                wav = await ai.speech(text, voice)
            except ai.AIError:
                return None
            name = f"{secrets.token_urlsafe(8)}.wav"
            (d / name).write_bytes(wav)
            return {"seq": seq, "url": f"{s.public_url}/files/agent/{uid}/{name}", "sec": round(wav_seconds(wav), 2), "text": text}

        async def producer():
            nonlocal heard
            buf, seq, pre = "", 0, ""
            convo = list(msgs)
            for _ in range(4):                      # up to 3 tool rounds
                calls = None
                async for kind, val in ai.stream_events(MODEL, convo, TOOLS):
                    if kind == "tools":
                        calls = val; continue
                    if heard is None:                # strip the [[transcript]] prefix
                        pre += val
                        if "]]" in pre or (len(pre) > 400):
                            m = re.match(r"\s*\[\[(.*?)\]\]\s*", pre, re.S)
                            heard = (m.group(1).strip() if m else "")
                            await emit({"type": "heard", "text": heard})
                            val = pre[m.end():] if m else pre
                        else:
                            continue
                    if not val:
                        continue
                    answer.append(val); buf += val
                    await emit({"type": "text", "t": val})
                    ready, buf = split_ready(buf, seq == 0)
                    for sent in ready:
                        tts_tasks.append(asyncio.create_task(speak(seq, sent))); seq += 1
                if heard is None:                   # round ended (e.g. tool call) before the transcript was closed
                    m = re.match(r"\s*\[\[(.*?)\]\]\s*", pre, re.S)
                    heard = m.group(1).strip() if m else ""
                    await emit({"type": "heard", "text": heard})
                    rest = pre[m.end():] if m else pre.replace("[[", "").replace("]]", "")
                    pre = ""
                    if rest.strip():
                        answer.append(rest); buf += rest
                        await emit({"type": "text", "t": rest})
                if not calls:
                    break
                convo.append({"role": "assistant", "content": "".join(answer) or None,
                              "tool_calls": [{"id": c["id"] or f"c{i}", "type": "function", "function": {"name": c["name"], "arguments": c["arguments"] or "{}"}}
                                             for i, c in enumerate(calls)]})
                for i, c in enumerate(calls):
                    if c["name"] == "web_search":
                        searches.append(1)
                    try:
                        args = json.loads(c["arguments"] or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    res = await run_tool(c["name"], args, u, emit)
                    convo.append({"role": "tool", "tool_call_id": c["id"] or f"c{i}", "content": res})
            if buf.strip():
                tts_tasks.append(asyncio.create_task(speak(seq, buf.strip())))
            await emit({"type": "_textdone"})

        async def voices_in_order():
            sent = 0
            while True:
                while sent < len(tts_tasks):
                    a = await tts_tasks[sent]
                    sent += 1
                    if a:
                        nonlocal_out.append(a["sec"])
                        await emit({"type": "audio", **a})
                if done_flag.is_set() and sent >= len(tts_tasks):
                    return
                await asyncio.sleep(0.05)

        nonlocal_out: list[float] = []
        searches: list[int] = []
        done_flag = asyncio.Event()

        async def run():
            try:
                await producer()
            except ai.AIError:
                await emit({"type": "error", "text": "Модель сейчас перегружена, попробуйте ещё раз"})
            finally:
                done_flag.set()

        prod = asyncio.create_task(run())
        speaker = asyncio.create_task(voices_in_order())
        finished = False
        while not finished:
            try:
                o = await asyncio.wait_for(q.get(), timeout=0.2)
            except asyncio.TimeoutError:
                if prod.done() and speaker.done() and q.empty():
                    finished = True
                continue
            if o.get("type") == "_textdone":
                continue
            yield _sse(o)
        await prod
        out_sec = sum(nonlocal_out)
        reply = "".join(answer).strip()
        price = max(1, math.ceil((in_sec + out_sec) / 60 * PRICE["agent_min"])) if (reply or heard) else 0
        price += len(searches) * int(PRICE.get("agent_search", 0))
        bal = None
        async with Session() as db2:
            user = await db2.get(User, uid)
            if heard:
                db2.add(ChatMessage(user_id=uid, role="user", text=heard, channel="agent"))
            if reply:
                db2.add(ChatMessage(user_id=uid, role="model", text=reply, channel="agent"))
            if price:
                await charge(db2, user, min(price, user.balance), "Агент: разговор" + (" и поиск" if searches else ""), None)
            await db2.commit()
            bal = user.balance
        yield _sse({"type": "done", "balance": bal, "cost": price, "heard": heard or ""})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
