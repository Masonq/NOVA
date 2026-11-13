from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Job, User
from ..security import current_user
from ..storage import public_files, remove_job_files

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


@router.get("/{jid}")
async def get_job(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    return job_out(await _own(db, u, jid))


@router.post("/{jid}/favorite")
async def toggle_favorite(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    j = await _own(db, u, jid)
    j.favorite = not j.favorite
    await db.commit()
    return {"favorite": j.favorite}


@router.delete("/{jid}")
async def delete_job(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    j = await _own(db, u, jid)
    remove_job_files(j)
    await db.delete(j)
    await db.commit()
    return {"ok": True}
