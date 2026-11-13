"""Credit packs and payment providers. Credits are granted exactly once per payment (row lock + status)."""
import logging
import secrets

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import bot
from .config import get_settings
from .credits import grant
from .models import Payment, User, now

log = logging.getLogger("nova.pay")
PACKS = [
    {"id": "p500", "credits": 500, "bonus": 0, "stars": 400, "usd": "4.99"},
    {"id": "p1500", "credits": 1500, "bonus": 150, "stars": 1150, "usd": "14.99", "hit": True},
    {"id": "p5000", "credits": 5000, "bonus": 1000, "stars": 3700, "usd": "44.99"},
]
BY_ID = {p["id"]: p for p in PACKS}
CRYPTO_API = "https://pay.crypt.bot/api"


def total(p: dict) -> int:
    return p["credits"] + p["bonus"]


def new_payload() -> str:
    return "nova_" + secrets.token_urlsafe(18)


async def credit(db: AsyncSession, pay_id: int, external_id: str = "") -> Payment | None:
    """Marks a payment paid and grants credits. Safe to call twice."""
    p = (await db.execute(select(Payment).where(Payment.id == pay_id).with_for_update())).scalar_one_or_none()
    if p is None or p.status == "paid":
        return None
    p.status, p.paid_at = "paid", now()
    if external_id:
        p.external_id = external_id
    u = await db.get(User, p.user_id)
    pk = BY_ID.get(p.pack, {})
    price = f"{p.amount} ⭐" if p.currency == "XTR" else f"${p.amount}"
    await grant(db, u, p.credits, "purchase", f"Пополнение: {p.credits} кредитов ({price})")
    await db.commit()
    log.info("payment %s paid: user %s +%s", p.id, p.user_id, p.credits)
    if u.can_message:
        bonus = f" (из них {pk.get('bonus')} бонусом)" if pk.get("bonus") else ""
        await bot.send(u.tg_id, f"✅ Оплата прошла: +{p.credits} кредитов{bonus}.\nБаланс: {u.balance}.", bot.open_app_markup("Открыть NOVA"))
    return p


# ---------- Telegram Stars ----------
async def stars_invoice(db: AsyncSession, u: User, pack: dict) -> tuple[Payment, str]:
    p = Payment(user_id=u.id, method="stars", pack=pack["id"], credits=total(pack), amount=str(pack["stars"]), currency="XTR", payload=new_payload())
    db.add(p)
    await db.flush()
    r = await bot.call("createInvoiceLink", {
        "title": f"NOVA · {total(pack)} кредитов",
        "description": "Кредиты для генераций и разговоров с агентом" + (f". Бонус +{pack['bonus']}" if pack["bonus"] else ""),
        "payload": p.payload, "currency": "XTR", "provider_token": "",
        "prices": [{"label": f"{total(pack)} кредитов", "amount": pack["stars"]}],
    })
    if not r.get("ok"):
        raise RuntimeError(r.get("description") or "Telegram не создал счёт")
    await db.commit()
    return p, r["result"]


# ---------- Crypto Pay (@CryptoBot) ----------
async def crypto_call(method: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=20) as cl:
        r = await cl.post(f"{CRYPTO_API}/{method}", headers={"Crypto-Pay-API-Token": get_settings().crypto_pay_token}, json=payload)
    d = r.json()
    if not d.get("ok"):
        raise RuntimeError(str(d.get("error") or d)[:200])
    return d["result"]


async def crypto_invoice(db: AsyncSession, u: User, pack: dict) -> tuple[Payment, str]:
    p = Payment(user_id=u.id, method="crypto", pack=pack["id"], credits=total(pack), amount=pack["usd"], currency="USD", payload=new_payload())
    db.add(p)
    await db.flush()
    inv = await crypto_call("createInvoice", {
        "currency_type": "fiat", "fiat": "USD", "amount": pack["usd"], "accepted_assets": "USDT,TON,BTC,ETH,LTC,TRX,USDC",
        "description": f"NOVA · {total(pack)} кредитов", "payload": p.payload, "expires_in": 3600,
        "allow_comments": False, "allow_anonymous": True,
    })
    p.external_id = str(inv["invoice_id"])
    await db.commit()
    return p, inv.get("mini_app_invoice_url") or inv.get("bot_invoice_url")


async def crypto_sync(db: AsyncSession, payments: list[Payment]) -> int:
    """Asks Crypto Pay about pending invoices; grants credits for paid ones. Returns how many got paid."""
    ids = [p.external_id for p in payments if p.method == "crypto" and p.status == "pending" and p.external_id]
    if not ids or not get_settings().crypto_pay_token:
        return 0
    items = (await crypto_call("getInvoices", {"invoice_ids": ",".join(ids)})).get("items", [])
    by_ext = {p.external_id: p for p in payments}
    n = 0
    for it in items:
        p = by_ext.get(str(it.get("invoice_id")))
        if not p:
            continue
        if it.get("status") == "paid":
            if await credit(db, p.id, str(it.get("invoice_id"))):
                n += 1
        elif it.get("status") == "expired" and p.status == "pending":
            p.status = "expired"
            await db.commit()
    return n
