from test_core import login, A


def test_real_defaults():
    import importlib, app.pricing as p
    src = open(p.__file__).read()
    assert '"welcome": 100,' in src and '"ref_friend": 50,' in src and '"image_edit": 18,' in src
    assert '"agent_search": 3,' in src and '"chat_msg": 1,' in src


@A
async def test_photo_edit_price_and_old_admin_values_ignored(client):
    from app.db import Session
    from app.models import Setting
    from app import pricing
    h = await login(client, 4401)
    up = (await client.post("/api/uploads", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50, "image/png")}, headers=h)).json()["url"]
    q = lambda p: client.post("/api/jobs/price", json={"kind": "image", "prompt": "x y", "params": p}, headers=h)
    assert (await q({})).json()["cost"] == 12 and (await q({"refs": [up]})).json()["cost"] == 18
    async with Session() as db:          # an admin override saved with an old default value must not win
        old = await db.get(Setting, "prices")
        before = dict(old.value) if old else None
        await db.merge(Setting(key="prices", value={"price": {"welcome": 300, "image": 40, "music": 33}, "packs": pricing.DEFAULT_PACKS}))
        await db.commit()
        await pricing.refresh(db, force=True)
    assert pricing.PRICE["image"] == 12 and pricing.PRICE["music"] == 33
    async with Session() as db:
        row = await db.get(Setting, "prices")
        if before is None:
            await db.delete(row)
        else:
            row.value = before
        await db.commit()
        await pricing.refresh(db, force=True)


@A
async def test_chat_costs_one_credit_one_ledger_line_refund_on_failure(client, monkeypatch):
    from app.routes import chat as ch
    from app.ai import AIError
    async def ok(models, contents, system):
        yield "Привет!"
    monkeypatch.setattr(ch, "stream_text", ok)
    h = await login(client, 4402)
    bal = (await client.get("/api/me", headers=h)).json()["balance"]
    for _ in range(3):
        r = await client.post("/api/chat", json={"text": "привет"}, headers=h)
        assert "Привет" in r.text
    assert (await client.get("/api/me", headers=h)).json()["balance"] == bal - 3
    led = (await client.get("/api/me/ledger", headers=h)).json()
    chat_rows = [l for l in led if l["title"].startswith("Текстовый чат")]
    assert len(chat_rows) == 1 and chat_rows[0]["delta"] == -3 and chat_rows[0]["title"] == "Текстовый чат: 3 сообщения"
    async def bad(models, contents, system):
        raise AIError("down")
        yield ""
    monkeypatch.setattr(ch, "stream_text", bad)
    r = await client.post("/api/chat", json={"text": "ещё"}, headers=h)
    assert "кредит вернулся" in r.text
    assert (await client.get("/api/me", headers=h)).json()["balance"] == bal - 3
