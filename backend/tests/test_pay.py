import json
import pytest
from test_core import login, A
from app import bot, payments as P
from app.config import get_settings


@pytest.fixture
def tg(monkeypatch):
    calls = []
    async def call(method, payload):
        calls.append((method, payload))
        if method == "createInvoiceLink":
            return {"ok": True, "result": "https://t.me/$inv123"}
        return {"ok": True, "result": True}
    async def send(chat_id, text, markup=None):
        calls.append(("send", {"chat_id": chat_id, "text": text}))
    monkeypatch.setattr(bot, "call", call)
    monkeypatch.setattr(bot, "send", send)
    return calls


async def hook(client, upd):
    return await client.post("/api/tg/webhook", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": get_settings().webhook_secret})


@A
async def test_stars_full_flow(client, tg):
    h = await login(client, 7701)
    me = (await client.get("/api/me", headers=h)).json()
    packs = (await client.get("/api/pay/packs", headers=h)).json()
    assert [p["total"] for p in packs["packs"]] == [500, 1650, 6000] and packs["methods"] == ["stars"]
    r = (await client.post("/api/pay/stars", json={"pack": "p1500"}, headers=h)).json()
    assert r["link"].startswith("https://t.me/") and r["payment"]["status"] == "pending"
    inv = next(c for c in tg if c[0] == "createInvoiceLink")[1]
    assert inv["currency"] == "XTR" and inv["prices"][0]["amount"] == 1150 and inv["provider_token"] == ""
    payload = inv["payload"]
    # wrong amount is refused, correct one accepted
    await hook(client, {"update_id": 1, "pre_checkout_query": {"id": "q1", "from": {"id": 7701}, "currency": "XTR", "total_amount": 1, "invoice_payload": payload}})
    await hook(client, {"update_id": 2, "pre_checkout_query": {"id": "q2", "from": {"id": 7701}, "currency": "XTR", "total_amount": 1150, "invoice_payload": payload}})
    answers = [c[1] for c in tg if c[0] == "answerPreCheckoutQuery"]
    assert answers[0]["ok"] is False and answers[1]["ok"] is True
    # someone else cannot pay this invoice
    await hook(client, {"update_id": 3, "pre_checkout_query": {"id": "q3", "from": {"id": 999}, "currency": "XTR", "total_amount": 1150, "invoice_payload": payload}})
    assert [c[1] for c in tg if c[0] == "answerPreCheckoutQuery"][-1]["ok"] is False
    paid = {"update_id": 4, "message": {"message_id": 5, "chat": {"id": 7701, "type": "private"}, "from": {"id": 7701, "first_name": "T"},
            "successful_payment": {"currency": "XTR", "total_amount": 1150, "invoice_payload": payload, "telegram_payment_charge_id": "ch_1"}}}
    await hook(client, paid)
    await hook(client, {**paid, "update_id": 5})            # duplicate delivery must not credit twice
    st = (await client.get(f"/api/pay/{r['payment']['id']}", headers=h)).json()
    assert st["status"] == "paid" and st["balance"] == me["balance"] + 1650
    led = (await client.get("/api/me/ledger", headers=h)).json()
    assert led[0]["kind"] == "purchase" and led[0]["delta"] == 1650 and sum(1 for l in led if l["kind"] == "purchase") == 1
    assert any(c[0] == "send" and "+1650" in c[1]["text"] for c in tg)


@A
async def test_crypto_flow(client, tg, monkeypatch):
    monkeypatch.setattr(get_settings(), "crypto_pay_token", "tok")
    state = {"status": "active"}
    async def crypto_call(method, payload):
        if method == "createInvoice":
            assert payload["amount"] == "4.99" and payload["fiat"] == "USD"
            return {"invoice_id": 55, "mini_app_invoice_url": "https://t.me/CryptoBot/app?startapp=x"}
        if method == "getInvoices":
            return {"items": [{"invoice_id": 55, "status": state["status"]}]}
    monkeypatch.setattr(P, "crypto_call", crypto_call)
    h = await login(client, 7702)
    bal = (await client.get("/api/me", headers=h)).json()["balance"]
    assert "crypto" in (await client.get("/api/pay/packs", headers=h)).json()["methods"]
    r = (await client.post("/api/pay/crypto", json={"pack": "p500"}, headers=h)).json()
    pid = r["payment"]["id"]
    assert (await client.get(f"/api/pay/{pid}", headers=h)).json()["status"] == "pending"
    state["status"] = "paid"
    s1 = (await client.get(f"/api/pay/{pid}", headers=h)).json()
    s2 = (await client.get(f"/api/pay/{pid}", headers=h)).json()
    assert s1["status"] == "paid" and s2["balance"] == bal + 500


@A
async def test_bad_pack_and_foreign_payment(client, tg):
    h1 = await login(client, 7703); h2 = await login(client, 7704)
    assert (await client.post("/api/pay/stars", json={"pack": "x"}, headers=h1)).status_code == 404
    assert (await client.post("/api/pay/crypto", json={"pack": "p500"}, headers=h1)).status_code == 503
    pid = (await client.post("/api/pay/stars", json={"pack": "p500"}, headers=h1)).json()["payment"]["id"]
    assert (await client.get(f"/api/pay/{pid}", headers=h2)).status_code == 404
