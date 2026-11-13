"""Exact spend tracking. Every model call is recorded with the cost the provider reports and the job/user it belongs to.
The context (job, user, kind) travels with the asyncio task, so low-level clients don't need to know about it."""
import asyncio
import contextvars
import logging

import httpx

from .config import get_settings

log = logging.getLogger("nova.costs")
ctx: contextvars.ContextVar[dict] = contextvars.ContextVar("cost_ctx", default={})
KIE_USD_PER_CREDIT = 0.005          # Kie sells 1 000 credits for $5
_pending: set = set()


def set_ctx(**kw):
    ctx.set({**ctx.get(), **kw})


async def _save(provider: str, usd: float, note: str, c: dict):
    from .db import Session
    from .models import Cost
    try:
        async with Session() as db:
            db.add(Cost(provider=provider, usd=float(usd or 0), kind=c.get("kind", "other"), job_id=c.get("job_id"),
                        user_id=c.get("user_id"), note=note[:120]))
            await db.commit()
    except Exception as e:
        log.warning("cost not saved: %s", e)


def _spawn(coro):
    t = asyncio.create_task(coro)
    _pending.add(t)
    t.add_done_callback(_pending.discard)


def record(provider: str, usd: float, note: str = ""):
    if usd and usd > 0:
        _spawn(_save(provider, usd, note, dict(ctx.get())))


async def _lookup(gen_id: str, note: str, c: dict):
    """OpenRouter posts the final cost of a generation a moment after it ends."""
    s = get_settings()
    for wait in (2, 4, 8, 16):
        await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=15) as cl:
                r = await cl.get("https://openrouter.ai/api/v1/generation", params={"id": gen_id},
                                 headers={"Authorization": f"Bearer {s.openrouter_key}"})
            if r.status_code == 200:
                d = r.json().get("data") or {}
                usd = d.get("total_cost") or d.get("usage")
                if usd is not None:
                    await _save("openrouter", float(usd), note, c)
                    return
        except Exception:
            pass
    log.warning("no cost for generation %s", gen_id)


def openrouter(resp: dict | None = None, note: str = "", gen_id: str | None = None):
    """Takes usage.cost from a response when it is there, otherwise looks the generation up by its id."""
    usage = (resp or {}).get("usage") or {}
    if usage.get("cost") is not None:
        record("openrouter", float(usage["cost"]), note)
        return
    gid = gen_id or (resp or {}).get("id")
    if gid:
        _spawn(_lookup(gid, note, dict(ctx.get())))


def kie(credits, note: str = ""):
    try:
        record("kie", float(credits) * KIE_USD_PER_CREDIT, note)
    except (TypeError, ValueError):
        pass


async def balances() -> dict:
    """Live balances for the admin panel."""
    s = get_settings()
    out = {}
    async with httpx.AsyncClient(timeout=15) as cl:
        try:
            h = {"Authorization": f"Bearer {s.openrouter_key}"}
            cr = (await cl.get("https://openrouter.ai/api/v1/credits", headers=h)).json().get("data")
            key = (await cl.get("https://openrouter.ai/api/v1/key", headers=h)).json().get("data") or {}
            if not isinstance(cr, dict) or "total_credits" not in cr:
                raise ValueError("no data")
            out["openrouter"] = {"left": round(float(cr.get("total_credits", 0)) - float(cr.get("total_usage", 0)), 2),
                                 "key_used": round(float(key.get("usage") or 0), 2), "key_limit": key.get("limit")}
        except Exception as e:
            out["openrouter"] = {"error": type(e).__name__}
        try:
            tr = httpx.AsyncHTTPTransport(local_address="0.0.0.0")
            async with httpx.AsyncClient(timeout=15, transport=tr) as k:
                d = (await k.get("https://api.kie.ai/api/v1/chat/credit", headers={"Authorization": f"Bearer {s.kie_key}"})).json()
            if d.get("code") != 200 or d.get("data") is None:
                raise ValueError(str(d.get("msg"))[:60])
            cred = float(d["data"])
            out["kie"] = {"credits": cred, "usd": round(cred * KIE_USD_PER_CREDIT, 2)}
        except Exception as e:
            out["kie"] = {"error": type(e).__name__}
    return out



async def _alert(provider: str, text: str):
    """Tells the admins in Telegram that a provider is out of money — at most once an hour per provider."""
    try:
        from .queue import pool
        from . import bot
        r = await pool()
        if not await r.set(f"nova:alert:funds:{provider}", "1", ex=3600, nx=True):
            return
        for tid in [x for x in get_settings().admin_tg_ids.replace(" ", "").split(",") if x.isdigit()]:
            await bot.send(int(tid), text)
    except Exception as e:
        log.warning("funds alert: %s", e)


def out_of_funds(provider: str, detail: str = ""):
    names = {"openrouter": "OpenRouter (фото, голос, чат, агент)", "kie": "Kie (видео, музыка)"}
    where = {"openrouter": "openrouter.ai → Credits, и проверьте лимит ключа в Settings → Keys", "kie": "kie.ai → Billing"}
    _spawn(_alert(provider, f"⚠️ На {names.get(provider, provider)} закончились деньги — генерации не проходят.\n"
                            f"Пополните: {where.get(provider, '')}.\n{detail[:120]}"))
