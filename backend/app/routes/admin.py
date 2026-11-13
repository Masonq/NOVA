"""Admin panel API (visible only to ADMIN_TG_IDS). Every change is written to the admin log."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import Date, cast, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import bot, pricing
from ..credits import grant
from ..db import get_db
from ..models import AdminLog, Broadcast, Job, Ledger, Payment, PromoCode, PromoUse, Setting, User, now
from ..queue import pool
from ..security import admin_user
from ..storage import remove_job_files
from .jobs import job_out

router = APIRouter(prefix="/api/admin", tags=["admin"])
RUB_PER_USD = 90   # for the revenue estimate only
COST_USD = {"image": 0.04, "video_s": 0.08, "music": 0.08, "tts_1k": 0.017, "agent_turn": 0.003}   # rough model cost


async def log(db, a: User, action: str, target: str = "", detail: str = ""):
    db.add(AdminLog(admin_id=a.id, action=action, target=target, detail=detail[:2000]))


def uout(u: User) -> dict:
    return {"id": u.id, "tg_id": u.tg_id, "name": u.first_name, "username": u.username, "balance": u.balance,
            "blocked": u.blocked, "created": u.created_at.isoformat(), "seen": u.last_seen.isoformat() if u.last_seen else None}


# ---------------- stats ----------------
@router.get("/stats")
async def stats(days: int = 30, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    days = max(7, min(days, 90))
    since = now() - timedelta(days=days)
    total = (await db.execute(select(func.count(User.id)))).scalar_one()
    dau = (await db.execute(select(func.count(User.id)).where(User.last_seen > now() - timedelta(days=1)))).scalar_one()
    wau = (await db.execute(select(func.count(User.id)).where(User.last_seen > now() - timedelta(days=7)))).scalar_one()
    day = cast(func.timezone("UTC", User.created_at), Date)
    new = dict((str(d), n) for d, n in (await db.execute(select(day, func.count()).where(User.created_at > since).group_by(day))).all())
    pday = cast(func.timezone("UTC", Payment.paid_at), Date)
    pays = (await db.execute(select(pday, Payment.currency, func.count(), func.sum(cast(Payment.amount, pricing_float())))
                             .where(Payment.status == "paid", Payment.paid_at > since).group_by(pday, Payment.currency))).all()
    jday = cast(func.timezone("UTC", Job.created_at), Date)
    jobs = (await db.execute(select(jday, Job.kind, Job.status, func.count(), func.sum(Job.cost))
                             .where(Job.created_at > since).group_by(jday, Job.kind, Job.status))).all()
    spent = (await db.execute(select(func.coalesce(func.sum(-Ledger.delta), 0)).where(Ledger.kind == "charge", Ledger.created_at > since))).scalar_one()
    agent_turns = (await db.execute(select(func.count()).select_from(Ledger).where(Ledger.title.like("Агент: разговор%"), Ledger.created_at > since))).scalar_one()
    series = []
    for i in range(days - 1, -1, -1):
        d = str((datetime.now(timezone.utc) - timedelta(days=i)).date())
        series.append({"day": d, "users": new.get(d, 0),
                       "stars": sum(int(s or 0) for dd, c, n, s in pays if str(dd) == d and c == "XTR"),
                       "usd": round(sum(float(s or 0) for dd, c, n, s in pays if str(dd) == d and c == "USD"), 2),
                       "rub": round(sum(float(s or 0) for dd, c, n, s in pays if str(dd) == d and c == "RUB")),
                       "jobs": sum(n for dd, k, st, n, c in jobs if str(dd) == d)})
    by_kind = {}
    for d, k, st, n, c in jobs:
        x = by_kind.setdefault(k, {"total": 0, "done": 0, "failed": 0, "review": 0, "credits": 0})
        x["total"] += n
        if st in ("done", "failed", "review"):
            x[st] += n
        if st == "done":
            x["credits"] += int(c or 0)
    stars = sum(r["stars"] for r in series); usd = sum(r["usd"] for r in series); rub = sum(r["rub"] for r in series)
    revenue = round(stars * 0.013 + usd * 0.97 + rub * 0.965 / RUB_PER_USD, 2)   # Stars ~$0.013, Crypto Pay ~3%, YooKassa ~3.5%
    vid_sec = (await db.execute(select(func.coalesce(func.sum(cast(Job.params["duration"].as_string(), pricing_float())), 0))
                                .where(Job.kind == "video", Job.status == "done", Job.created_at > since))).scalar_one()
    cost = (by_kind.get("image", {}).get("done", 0) * COST_USD["image"] + float(vid_sec or 0) * COST_USD["video_s"]
            + by_kind.get("music", {}).get("done", 0) * COST_USD["music"] + agent_turns * COST_USD["agent_turn"])
    return {"days": days, "users": {"total": total, "dau": dau, "wau": wau}, "series": series, "by_kind": by_kind,
            "money": {"stars": stars, "usd": round(usd, 2), "rub": rub, "revenue_usd": revenue, "cost_usd": round(cost, 2),
                      "margin_usd": round(revenue - cost, 2), "credits_spent": int(spent), "agent_turns": agent_turns}}


def pricing_float():
    from sqlalchemy import Float
    return Float


# ---------------- users ----------------
@router.get("/users")
async def users(q: str = "", offset: int = 0, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    s = select(User)
    if q.strip():
        t = q.strip().lstrip("@")
        conds = [User.first_name.ilike(f"%{t}%"), User.username.ilike(f"%{t}%")]
        if t.isdigit():
            conds += [User.tg_id == int(t), User.id == int(t)]
        s = s.where(or_(*conds))
    rows = (await db.execute(s.order_by(User.last_seen.desc()).offset(max(0, offset)).limit(50))).scalars().all()
    return [uout(u) for u in rows]


@router.get("/users/{uid}")
async def user(uid: int, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    u = await db.get(User, uid)
    if not u:
        raise HTTPException(404, "Нет такого пользователя")
    led = (await db.execute(select(Ledger).where(Ledger.user_id == uid).order_by(Ledger.id.desc()).limit(30))).scalars().all()
    js = (await db.execute(select(Job).where(Job.user_id == uid).order_by(Job.id.desc()).limit(20))).scalars().all()
    paid = (await db.execute(select(Payment.currency, func.sum(cast(Payment.amount, pricing_float())))
                             .where(Payment.user_id == uid, Payment.status == "paid").group_by(Payment.currency))).all()
    return {**uout(u), "paid": {c: float(s or 0) for c, s in paid},
            "ledger": [{"delta": l.delta, "title": l.title, "kind": l.kind, "at": l.created_at.isoformat()} for l in led],
            "jobs": [job_out(j) for j in js]}


class CreditsIn(BaseModel):
    delta: int = Field(ge=-100000, le=100000)
    reason: str = Field(min_length=2, max_length=200)


@router.post("/users/{uid}/credits")
async def credits(uid: int, body: CreditsIn, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    u = await db.get(User, uid)
    if not u or body.delta == 0:
        raise HTTPException(404, "Нет такого пользователя")
    if body.delta > 0:
        await grant(db, u, body.delta, "admin", f"Начислено: {body.reason}")
    else:
        from ..credits import _locked
        lu = await _locked(db, u)
        take = min(-body.delta, lu.balance)
        lu.balance -= take
        db.add(Ledger(user_id=u.id, delta=-take, balance_after=lu.balance, kind="admin", title=f"Списано: {body.reason}"))
    await log(db, a, "credits", f"user {uid}", f"{body.delta:+d}: {body.reason}")
    await db.commit()
    return uout(u)


class BlockIn(BaseModel):
    blocked: bool


@router.post("/users/{uid}/block")
async def block(uid: int, body: BlockIn, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    u = await db.get(User, uid)
    if not u or u.id == a.id:
        raise HTTPException(400, "Нельзя")
    u.blocked = body.blocked
    await log(db, a, "block" if body.blocked else "unblock", f"user {uid}")
    await db.commit()
    return uout(u)


# ---------------- jobs ----------------
@router.get("/jobs")
async def jobs(kind: str = "", status: str = "", offset: int = 0, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    s = select(Job, User).join(User, User.id == Job.user_id)
    if kind:
        s = s.where(Job.kind == kind)
    if status:
        s = s.where(Job.status == status)
    rows = (await db.execute(s.order_by(Job.id.desc()).offset(max(0, offset)).limit(40))).all()
    return [{**job_out(j), "user": {"id": u.id, "name": u.first_name, "username": u.username}, "moderation": j.moderation, "error": j.error}
            for j, u in rows]


@router.delete("/jobs/{jid}")
async def remove(jid: int, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    j = await db.get(Job, jid)
    if not j:
        raise HTTPException(404, "Нет такой работы")
    remove_job_files(j)
    await log(db, a, "delete_job", f"job {jid}", j.prompt[:200])
    await db.delete(j)
    await db.commit()
    return {"ok": True}


# ---------------- prices ----------------
@router.get("/prices")
async def prices(a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    await pricing.refresh(db, force=True)
    return {"price": pricing.PRICE, "packs": pricing.PACKS, "defaults": {"price": pricing.DEFAULT_PRICE, "packs": pricing.DEFAULT_PACKS}}


class PricesIn(BaseModel):
    price: dict
    packs: list[dict]


@router.put("/prices")
async def set_prices(body: PricesIn, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    price = {}
    for k, v in body.price.items():
        if k not in pricing.DEFAULT_PRICE:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            raise HTTPException(422, f"«{k}»: нужно число")
        if v < 0 or v > 100000:
            raise HTTPException(422, f"«{k}»: недопустимое значение")
        price[k] = int(v) if k != "video_sound_k" else round(v, 2)
    packs = []
    for i, p in enumerate(body.packs[:6]):
        try:
            pk = {"id": str(p.get("id") or f"p{i}")[:16], "credits": int(p["credits"]), "bonus": int(p.get("bonus") or 0),
                  "stars": int(p["stars"]), "usd": f"{float(p['usd']):.2f}", "rub": int(float(p.get("rub") or 0))}
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, f"Пакет {i + 1}: заполните кредиты, звёзды и цену в $")
        if pk["credits"] < 1 or pk["stars"] < 1 or float(pk["usd"]) < 0.5:
            raise HTTPException(422, f"Пакет {i + 1}: слишком маленькие значения")
        if p.get("hit"):
            pk["hit"] = True
        packs.append(pk)
    if not packs:
        raise HTTPException(422, "Нужен хотя бы один пакет")
    row = await db.get(Setting, "prices")
    val = {"price": price, "packs": packs}
    if row:
        row.value, row.updated_at = val, now()
    else:
        db.add(Setting(key="prices", value=val))
    await log(db, a, "prices", "", str(val))
    await db.commit()
    await pricing.refresh(db, force=True)
    return {"price": pricing.PRICE, "packs": pricing.PACKS}


# ---------------- promo codes ----------------
class PromoIn(BaseModel):
    code: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    credits: int = Field(ge=1, le=100000)
    max_uses: int = Field(ge=1, le=1000000)
    days: int | None = Field(default=None, ge=1, le=3650)


def pout(p: PromoCode) -> dict:
    return {"id": p.id, "code": p.code, "credits": p.credits, "max_uses": p.max_uses, "used": p.used, "active": p.active,
            "expires": p.expires_at.isoformat() if p.expires_at else None}


@router.get("/promos")
async def promos(a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    return [pout(p) for p in (await db.execute(select(PromoCode).order_by(PromoCode.id.desc()))).scalars().all()]


@router.post("/promos")
async def add_promo(body: PromoIn, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    code = body.code.upper()
    if (await db.execute(select(PromoCode.id).where(PromoCode.code == code))).first():
        raise HTTPException(409, "Такой код уже есть")
    p = PromoCode(code=code, credits=body.credits, max_uses=body.max_uses,
                  expires_at=now() + timedelta(days=body.days) if body.days else None)
    db.add(p)
    await log(db, a, "promo_add", code, f"{body.credits} кр × {body.max_uses}")
    await db.commit()
    return pout(p)


@router.post("/promos/{pid}/toggle")
async def toggle_promo(pid: int, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    p = await db.get(PromoCode, pid)
    if not p:
        raise HTTPException(404, "Нет такого кода")
    p.active = not p.active
    await log(db, a, "promo_on" if p.active else "promo_off", p.code)
    await db.commit()
    return pout(p)


# ---------------- broadcasts ----------------
class BroadcastIn(BaseModel):
    text: str = Field(min_length=2, max_length=3500)
    button: str = Field(default="", max_length=40)


@router.post("/broadcast/preview")
async def preview(body: BroadcastIn, a: User = Depends(admin_user)):
    r = await bot.send(a.tg_id, body.text, bot.open_app_markup(body.button) if body.button else None)
    if not r.get("ok"):
        raise HTTPException(422, f"Telegram не принял сообщение: {r.get('description', '')}")
    return {"ok": True}


@router.post("/broadcast")
async def broadcast(body: BroadcastIn, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    if (await db.execute(select(Broadcast.id).where(Broadcast.status.in_(("queued", "sending"))))).first():
        raise HTTPException(409, "Предыдущая рассылка ещё идёт")
    total = (await db.execute(select(func.count(User.id)).where(User.can_message.is_(True), User.blocked.is_(False)))).scalar_one()
    b = Broadcast(text=body.text, button=body.button, total=total)
    db.add(b)
    await db.flush()
    await log(db, a, "broadcast", f"#{b.id}", body.text[:300])
    await db.commit()
    await (await pool()).enqueue_job("send_broadcast", b.id, _job_id=f"bc-{b.id}")
    return {"id": b.id, "total": total, "status": b.status}


@router.get("/broadcasts")
async def broadcasts(a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Broadcast).order_by(Broadcast.id.desc()).limit(10))).scalars().all()
    return [{"id": b.id, "text": b.text[:200], "button": b.button, "status": b.status, "total": b.total, "sent": b.sent,
             "failed": b.failed, "at": b.created_at.isoformat()} for b in rows]


@router.post("/broadcasts/{bid}/cancel")
async def cancel_broadcast(bid: int, a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    b = await db.get(Broadcast, bid)
    if not b or b.status not in ("queued", "sending"):
        raise HTTPException(409, "Рассылка уже закончилась")
    b.status = "cancelled"
    await log(db, a, "broadcast_cancel", f"#{bid}")
    await db.commit()
    return {"ok": True}


# ---------------- log ----------------
@router.get("/log")
async def admin_log(a: User = Depends(admin_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AdminLog, User).join(User, User.id == AdminLog.admin_id, isouter=True)
                             .order_by(AdminLog.id.desc()).limit(100))).all()
    return [{"action": l.action, "target": l.target, "detail": l.detail, "at": l.created_at.isoformat(),
             "admin": (u.first_name or u.username) if u else str(l.admin_id)} for l, u in rows]
