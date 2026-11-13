import json, re
from test_core import login, A, init_data
from app.config import get_settings


async def hook(client, upd):
    return await client.post("/api/tg/webhook", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": get_settings().webhook_secret})


@A
async def test_share_page_and_random_folder(client, monkeypatch):
    from app import runner, ai
    from app.routes import jobs as jm
    async def nop(j): pass
    monkeypatch.setattr(jm, "enqueue", nop)
    from PIL import Image
    import io
    buf = io.BytesIO(); Image.new("RGB", (900, 900), (120, 40, 200)).save(buf, "PNG")
    async def img(prompt, aspect, refs, quality="fast"): return buf.getvalue()
    monkeypatch.setattr(ai, "image", img)
    h = await login(client, 5101)
    jid = (await client.post("/api/jobs", json={"kind": "image", "prompt": "Лиса в неоне", "params": {}}, headers=h)).json()["id"]
    await runner.run_job({}, jid)
    j = (await client.get(f"/api/jobs/{jid}", headers=h)).json()
    f = j["files"][0]
    assert re.search(rf"/files/\d+/{jid}_[0-9a-f]{{16}}/v1\.png$", f["url"]), f["url"]      # folder can't be guessed
    assert f["thumb_url"].endswith(".thumb.webp")
    r = (await client.post(f"/api/jobs/{jid}/share", headers=h)).json()
    assert r["url"].startswith("https://nova.test/s/")
    page = await client.get(r["url"].replace("https://nova.test", ""))
    assert page.status_code == 200 and 'property="og:image"' in page.text and "Лиса в неоне" in page.text and "start=ref_" in page.text
    h2 = await login(client, 5102)
    assert (await client.post(f"/api/jobs/{jid}/share", headers=h2)).status_code == 404     # only the owner shares
    assert (await client.get("/s/nope")).status_code == 404


@A
async def test_referral_by_bot_and_webapp_reward_once(client):
    inviter = await login(client, 5201)
    me = (await client.get("/api/me", headers=inviter)).json()
    ref = (await client.get("/api/me/referral", headers=inviter)).json()
    assert ref["link"].endswith(f"start=ref_{me['id']}") and ref["invited"] == 0
    # friend 1 comes through the bot
    await hook(client, {"update_id": 1, "message": {"message_id": 1, "chat": {"id": 5202, "type": "private"}, "from": {"id": 5202, "first_name": "Аня"}, "text": f"/start ref_{me['id']}"}})
    f1 = await login(client, 5202)
    assert (await client.get("/api/me", headers=f1)).json()["balance"] == 400               # 300 welcome + 100 friend bonus
    # friend 2 opens the mini app with start_param
    r = await client.post("/api/auth/webapp", json={"initData": init_data(5203, start_param=f"ref_{me['id']}")})
    f2 = {"Authorization": "Bearer " + r.json()["token"]}
    assert (await client.get("/api/me", headers=f2)).json()["balance"] == 400
    # self-referral and unknown referrer give nothing
    r = await client.post("/api/auth/webapp", json={"initData": init_data(5204, start_param="ref_999999")})
    assert (await client.get("/api/me", headers={"Authorization": "Bearer " + r.json()["token"]})).json()["balance"] == 300
    # friend 1 pays twice: inviter is rewarded once
    from app.db import Session
    from app.models import Payment
    from app import payments as P
    async with Session() as db:
        ids = []
        for i in range(2):
            p = Payment(user_id=(await client.get("/api/me", headers=f1)).json()["id"], method="stars", pack="p500", credits=500, amount="400", currency="XTR", payload=f"t{i}x")
            db.add(p); await db.flush(); ids.append(p.id)
        await db.commit()
        for pid in ids:
            await P.credit(db, pid, "ch")
    ref = (await client.get("/api/me/referral", headers=inviter)).json()
    assert ref["invited"] == 2 and ref["paid"] == 1 and ref["earned"] == 100
    assert (await client.get("/api/me", headers=inviter)).json()["balance"] == me["balance"] + 100
