"""«Свой исполнитель»: save the singer of a finished song as a Suno persona; new songs can be sung by it."""
import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import kie
from ..credits import charge, refund
from ..db import get_db
from ..models import Artist, Job, User, now
from ..pricing import PRICE, refresh as refresh_prices
from ..security import current_user

log = logging.getLogger("nova.artists")
router = APIRouter(prefix="/api/artists", tags=["artists"])
KIE_KEEPS_DAYS = 14          # Kie deletes generated audio after 14 days: a persona can only be made from a newer song
MAX_ARTISTS = 20


class ArtistIn(BaseModel):
    job_id: int
    name: str = Field(min_length=1, max_length=40)


def out(a: Artist) -> dict:
    return {"id": a.id, "name": a.name, "style": a.style, "job_id": a.job_id, "at": a.created_at.isoformat()}


@router.get("")
async def list_artists(u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Artist).where(Artist.user_id == u.id).order_by(Artist.id.desc()))).scalars().all()
    return [out(a) for a in rows]


@router.post("")
async def create_artist(body: ArtistIn, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    await refresh_prices(db)
    j = await db.get(Job, body.job_id)
    if not j or j.user_id != u.id or j.kind != "music" or j.status != "done":
        raise HTTPException(404, "Трек не найден или ещё не готов")
    p = j.params or {}
    f = next((x for x in (j.files or []) if x.get("type") == "audio"), None)
    if p.get("instrumental", True) or not f:
        raise HTTPException(422, "В этом треке нет вокала — исполнителя можно сохранить только из песни")
    if not f.get("task") or not f.get("sid"):
        raise HTTPException(422, "Из этого трека исполнителя сохранить нельзя — создайте новую песню")
    if j.created_at < now() - timedelta(days=KIE_KEEPS_DAYS):
        raise HTTPException(422, f"Исполнителя можно сохранить из песни не старше {KIE_KEEPS_DAYS} дней")
    mine = (await db.execute(select(Artist).where(Artist.user_id == u.id))).scalars().all()
    if any(a.job_id == j.id for a in mine):
        raise HTTPException(409, "Исполнитель из этой песни уже сохранён")
    if len(mine) >= MAX_ARTISTS:
        raise HTTPException(422, f"Можно сохранить до {MAX_ARTISTS} исполнителей — удалите лишних")
    name = " ".join(body.name.split())[:40]
    if any(a.name.lower() == name.lower() for a in mine):
        raise HTTPException(409, "Исполнитель с таким именем уже есть")
    price = int(PRICE.get("artist", 10))
    user = await db.get(User, u.id)
    await charge(db, user, price, f"Исполнитель: {name}", j.id)       # 402 when short
    await db.commit()
    brief = p.get("brief") or {}
    style = (brief.get("style") or p.get("genre") or "")[:300]
    vocals = {"male": "male vocal", "female": "female vocal", "duet": "male and female duet"}.get(brief.get("vocals"), "lead vocal")
    from .. import costs
    costs.set_ctx(user_id=u.id, kind="artist", job_id=j.id)
    try:
        pid = await kie.create_persona({"task_id": f["task"], "audio_id": f["sid"], "name": name,
                                        "description": f"{vocals}; {style}"[:500] or "lead vocal", "style": style[:200] or "pop",
                                        "vocal_start": 0, "vocal_end": max(10, min(30, int(f.get("duration") or 30)))})
    except kie.KieError as e:
        log.warning("persona for job %s failed: %s", j.id, e)
        user = await db.get(User, u.id)
        await refund(db, user, price, f"Возврат: исполнитель {name}", j.id)
        await db.commit()
        raise HTTPException(502, "Не получилось сохранить исполнителя — кредиты вернулись. Попробуйте позже")
    a = Artist(user_id=u.id, name=name, job_id=j.id, persona_id=pid, style=style)
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return {**out(a), "balance": (await db.get(User, u.id)).balance}


@router.delete("/{aid}")
async def delete_artist(aid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    a = await db.get(Artist, aid)
    if not a or a.user_id != u.id:
        raise HTTPException(404, "Не найдено")
    await db.delete(a)
    await db.commit()
    return {"ok": True}
