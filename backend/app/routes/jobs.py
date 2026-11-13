import io
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Job, User
from ..security import current_user
from ..config import get_settings
from ..credits import charge
from ..pricing import cost as price_of, refresh as refresh_prices
from ..queue import enqueue
from ..storage import new_upload_name, public_files, remove_job_files, upload_dir

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def job_out(j: Job) -> dict:
    return {"id": j.id, "kind": j.kind, "status": j.status, "prompt": j.prompt, "params": j.params,
            "progress": j.progress, "stage": j.stage, "files": public_files(j), "error": j.error,
            "favorite": j.favorite, "cost": j.cost, "at": j.created_at.isoformat(),
            "expires": j.expires_at.isoformat() if j.expires_at else None}


@router.get("")
async def list_jobs(kind: str | None = None, before: int | None = None, limit: int = 30,
                    u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    q = select(Job).where(Job.user_id == u.id, Job.status != "expired")
    if kind:
        q = q.where(Job.kind == kind)
    if before:
        q = q.where(Job.id < before)
    rows = (await db.execute(q.order_by(Job.id.desc()).limit(min(limit, 60)))).scalars().all()
    return [job_out(j) for j in rows]


async def _own(db: AsyncSession, u: User, jid: int) -> Job:
    j = await db.get(Job, jid)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "Не найдено")
    return j


class JobIn(BaseModel):
    kind: Literal["image", "video", "music", "tts", "clip", "reel", "greeting"]
    prompt: str = Field(min_length=2, max_length=5000)
    params: dict = {}


ALLOWED = {
    "image": {"style": {"Фото", "Арт", "Логотип", "3D", "Аниме"}, "aspect": {"1:1", "16:9", "9:16", "3:4", "4:3"}, "hq": {True, False}},
    "video": {"duration": {5, 10, 15}, "quality": {"720p", "1080p"}, "aspect": {"16:9", "9:16", "1:1"}},
    "music": {"genre": None, "mood": None, "instrumental": {True, False}, "voice_job": None, "voices": {"auto", "same", "male", "female", "duet"}},
    "clip": {"live": {True, False}, "subs": {True, False}},
    "reel": {"live": {True, False}, "subs": {True, False}, "music": {True, False}},
    "greeting": {"voices": {"auto", "male", "female", "duet"}},
    "tts": {"tone": {"Спокойно", "Бодро", "Шёпот", "Диктор"}},
}
LIMITS = {"image": 1200, "video": 1500, "music": 2900, "tts": 5000, "clip": 200, "reel": 500, "greeting": 600}
ACTIVE_LIMIT = 3
KIND_RU = {"image": "картинка", "video": "видео", "music": "трек", "tts": "озвучка", "clip": "клип", "reel": "ролик", "greeting": "поздравление"}


def _clean(kind: str, params: dict) -> dict:
    out = {}
    for k, allowed in ALLOWED[kind].items():
        if k in params:
            v = params[k]
            if allowed is not None and v not in allowed:
                raise HTTPException(422, f"Недопустимое значение «{k}»")
            out[k] = v if allowed is not None else (v if k == "voice_job" else str(v)[:60])
    s = get_settings()
    pub = s.public_url + "/files/"
    if kind == "image" and params.get("refs"):
        out["refs"] = [r for r in params["refs"][:4] if isinstance(r, str) and r.startswith(pub)]
    if kind == "video":
        out["sound"] = bool(params.get("sound"))
        if isinstance(params.get("image_url"), str) and params["image_url"].startswith(pub):
            out["image_url"] = params["image_url"]
    if kind == "clip":
        try:
            out["track_job"] = int(params.get("track_job"))
        except (TypeError, ValueError):
            raise HTTPException(422, "Не выбран трек")
    if kind == "reel":
        from ..ai import VOICES
        sc = params.get("scenes")
        if not isinstance(sc, list) or not 2 <= len(sc) <= 10:
            raise HTTPException(422, "В сценарии должно быть от 2 до 10 сцен")
        out["scenes"] = [{"text": str(x.get("text") or "").strip()[:300], "visual": str(x.get("visual") or "").strip()[:900]}
                         for x in sc if isinstance(x, dict)]
        if any(len(x["text"]) < 2 or len(x["visual"]) < 5 for x in out["scenes"]):
            raise HTTPException(422, "У каждой сцены должны быть текст и описание картинки")
        out["voice"] = params.get("voice") if params.get("voice") in VOICES else s.tts_voice
        out["title"] = str(params.get("title") or "")[:80]
        out["music_style"] = str(params.get("music_style") or "")[:200]
    if kind == "greeting":
        out["name"] = str(params.get("name") or "").strip()[:40]
        out["occasion"] = str(params.get("occasion") or "").strip()[:40]
        if len(out["name"]) < 1 or len(out["occasion"]) < 2:
            raise HTTPException(422, "Укажите имя и повод")
        parts = [x for x in (params.get("parts") or []) if x in ("song", "card", "video")]
        out["parts"] = parts or ["song", "card", "video"]
    if kind == "tts":
        from ..ai import VOICES
        out["voice"] = params.get("voice") if params.get("voice") in VOICES else s.tts_voice
        for k, g in (("male", "мужской"), ("female", "женский")):      # voices for marked parts
            v = params.get(k)
            if v in VOICES and g in VOICES[v]:
                out[k] = v
    return out


async def _track_source(db: AsyncSession, u: User, kind: str, params: dict) -> None:
    if kind != "clip":
        return
    src = await db.get(Job, params["track_job"])
    if not src or src.user_id != u.id or src.kind != "music" or src.status != "done" or not any(f.get("type") == "audio" for f in src.files or []):
        raise HTTPException(404, "Трек не найден или ещё не готов")


async def _voice_source(db: AsyncSession, u: User, kind: str, params: dict) -> None:
    """A track built around one of the user's voice-overs: check it and note its length (it is read again in rhythm)."""
    if kind != "music" or not params.get("voice_job"):
        return
    try:
        src = await db.get(Job, int(params["voice_job"]))
    except (TypeError, ValueError):
        src = None
    if not src or src.user_id != u.id or src.kind != "tts" or src.status != "done" or not src.files:
        raise HTTPException(404, "Озвучка не найдена или ещё не готова")
    params.update(voice_job=src.id, voice_chars=len(src.prompt), instrumental=False)


async def start_job(db: AsyncSession, u: User, kind: str, prompt: str, raw_params: dict) -> Job:
    """Validates, charges and queues a generation. Used by the API and by the voice agent."""
    await refresh_prices(db)
    prompt = prompt.strip()
    if len(prompt) > LIMITS[kind]:
        raise HTTPException(422, f"Слишком длинный текст: до {LIMITS[kind]} символов")
    params = _clean(kind, raw_params or {})
    active = (await db.execute(select(Job.id).where(Job.user_id == u.id, Job.status.in_(("review", "queued", "running"))))).all()
    if len(active) >= ACTIVE_LIMIT:
        raise HTTPException(429, "Уже идут 3 генерации — дождитесь, пока одна закончится")
    await _voice_source(db, u, kind, params)
    await _track_source(db, u, kind, params)
    price = price_of(kind, params, prompt)
    if u.balance < price:
        raise HTTPException(402, f"Не хватает кредитов: нужно {price}, на балансе {u.balance}")
    j = Job(user_id=u.id, kind=kind, prompt=prompt, params=params, cost=price, stage="В очереди", progress=2)
    db.add(j)
    await db.flush()
    await charge(db, u, price, {"image": "Фото", "video": "Видео", "music": "Музыка", "tts": "Озвучка", "clip": "Клип", "reel": "Ролик", "greeting": "Поздравление"}[kind] + ": " + prompt[:60], j.id)
    await db.commit()
    await enqueue(j.id)
    return j


@router.post("")
async def create_job(body: JobIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return job_out(await start_job(db, u, body.kind, body.prompt, body.params or {}))


@router.get("/active")
async def active_jobs(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Job).where(Job.user_id == u.id, Job.status.in_(("review", "queued", "running")))
                             .order_by(Job.id.desc()))).scalars().all()
    return [job_out(j) for j in rows]


@router.post("/price")
async def quote(body: JobIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await refresh_prices(db)
    params = _clean(body.kind, body.params or {})
    await _voice_source(db, u, body.kind, params)
    await _track_source(db, u, body.kind, params)
    return {"cost": price_of(body.kind, params, body.prompt.strip()), "balance": u.balance}


@router.get("/{jid}")
async def get_job(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return job_out(await _own(db, u, jid))


@router.post("/{jid}/favorite")
async def toggle_favorite(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    j = await _own(db, u, jid)
    j.favorite = not j.favorite
    await db.commit()
    return {"favorite": j.favorite}


@router.post("/{jid}/cancel")
async def cancel(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    from ..credits import refund
    j = await _own(db, u, jid)
    if j.status not in ("queued", "review"):
        raise HTTPException(409, "Генерация уже идёт — отменить можно только в очереди")
    j.status, j.stage = "cancelled", "Отменено"
    await refund(db, u, j.cost, "Возврат: генерация отменена", j.id)
    await db.commit()
    return job_out(j)


@router.delete("/{jid}")
async def delete_job(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    j = await _own(db, u, jid)
    remove_job_files(j)
    await db.delete(j)
    await db.commit()
    return {"ok": True}


upload_router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@upload_router.post("")
async def upload(file: UploadFile = File(...), u: User = Depends(current_user)):
    """Reference photo for image edit or the first frame of a video. JPEG/PNG/WebP up to 10 MB."""
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Фото больше 10 МБ")
    kinds = {b"\xff\xd8\xff": "jpg", b"\x89PNG": "png", b"RIFF": "webp"}
    ext = next((e for sig, e in kinds.items() if data.startswith(sig)), None)
    if not ext:
        raise HTTPException(415, "Нужно фото в JPG, PNG или WebP")
    name = new_upload_name(ext)
    (upload_dir(u.id) / name).write_bytes(data)
    return {"url": f"{get_settings().public_url}/files/{u.id}/uploads/{name}"}



class ScriptIn(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    seconds: Literal[30, 60] = 30


@router.post("/reel/script")
async def reel_script(body: ScriptIn, u: User = Depends(current_user)):
    """A draft script for a reel, to edit before the reel is made. Free, a few per minute."""
    from ..queue import pool
    r = await pool()
    key = f"nova:script:{u.id}"
    n = await r.incr(key)
    if n == 1:
        await r.expire(key, 60)
    if n > 6:
        raise HTTPException(429, "Слишком часто — подождите минуту")
    from .. import ai
    try:
        return await ai.reel_script(body.topic.strip(), body.seconds)
    except Exception as e:
        raise HTTPException(503, str(e) if isinstance(e, ai.AIError) else "Не получилось написать сценарий, попробуйте ещё раз")
