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
from ..pricing import cost as price_of
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
    kind: Literal["image", "video", "music", "tts"]
    prompt: str = Field(min_length=2, max_length=5000)
    params: dict = {}


ALLOWED = {
    "image": {"style": {"Фото", "Арт", "Логотип", "3D", "Аниме"}, "aspect": {"1:1", "16:9", "9:16", "3:4", "4:3"}},
    "video": {"duration": {5, 10, 15}, "quality": {"720p", "1080p"}, "aspect": {"16:9", "9:16", "1:1"}},
    "music": {"genre": None, "instrumental": {True, False}},
    "tts": {"tone": {"Спокойно", "Бодро", "Шёпот", "Диктор"}},
}
LIMITS = {"image": 1200, "video": 1500, "music": 2900, "tts": 5000}
ACTIVE_LIMIT = 3


def _clean(kind: str, params: dict) -> dict:
    out = {}
    for k, allowed in ALLOWED[kind].items():
        if k in params:
            v = params[k]
            if allowed is not None and v not in allowed:
                raise HTTPException(422, f"Недопустимое значение «{k}»")
            out[k] = v if allowed is not None else str(v)[:60]
    s = get_settings()
    pub = s.public_url + "/files/"
    if kind == "image" and params.get("refs"):
        out["refs"] = [r for r in params["refs"][:4] if isinstance(r, str) and r.startswith(pub)]
    if kind == "video":
        out["sound"] = bool(params.get("sound"))
        if isinstance(params.get("image_url"), str) and params["image_url"].startswith(pub):
            out["image_url"] = params["image_url"]
    if kind == "tts":
        from ..ai import VOICES
        out["voice"] = params.get("voice") if params.get("voice") in VOICES else s.tts_voice
    if kind == "music" and "mood" in params:
        out["mood"] = str(params["mood"])[:60]
    return out


@router.post("")
async def create_job(body: JobIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    prompt = body.prompt.strip()
    if len(prompt) > LIMITS[body.kind]:
        raise HTTPException(422, f"Слишком длинный текст: до {LIMITS[body.kind]} символов")
    params = _clean(body.kind, body.params or {})
    active = (await db.execute(select(Job.id).where(Job.user_id == u.id, Job.status.in_(("queued", "running"))))).all()
    if len(active) >= ACTIVE_LIMIT:
        raise HTTPException(429, "Уже идут 3 генерации — дождитесь, пока одна закончится")
    price = price_of(body.kind, params, prompt)
    j = Job(user_id=u.id, kind=body.kind, prompt=prompt, params=params, cost=price, stage="В очереди", progress=2)
    db.add(j)
    await db.flush()
    await charge(db, u, price, {"image": "Фото", "video": "Видео", "music": "Музыка", "tts": "Озвучка"}[body.kind] + ": " + prompt[:60], j.id)
    await db.commit()
    await enqueue(j.id)
    return job_out(j)


@router.get("/active")
async def active_jobs(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Job).where(Job.user_id == u.id, Job.status.in_(("queued", "running")))
                             .order_by(Job.id.desc()))).scalars().all()
    return [job_out(j) for j in rows]


@router.post("/price")
async def quote(body: JobIn, u: User = Depends(current_user)):
    return {"cost": price_of(body.kind, _clean(body.kind, body.params or {}), body.prompt.strip()), "balance": u.balance}


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
    if j.status != "queued":
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
