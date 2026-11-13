import pytest
from test_core import login, A
from app.config import get_settings


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_tg_ids", "6001")
    from app.routes import jobs as jm
    async def enq(jid): pass
    monkeypatch.setattr(jm, "enqueue", enq)
    from app.routes import admin as am
    monkeypatch.setattr(am, "enqueue", enq)


@A
async def test_admin_only(client, admin):
    hu = await login(client, 6002)
    assert (await client.get("/api/admin/stats", headers=hu)).status_code == 404
    ha = await login(client, 6001)
    assert (await client.get("/api/me", headers=ha)).json()["is_admin"] is True
    st = (await client.get("/api/admin/stats", headers=ha)).json()
    assert st["users"]["total"] >= 2 and len(st["series"]) == 30


@A
async def test_moderation_block_review_approve_reject(client, admin, monkeypatch, no_network):
    from app import moderation
    async def check(kind, prompt):
        return ("block", "x") if "запрет" in prompt else ("review", "известный человек") if "звезда" in prompt else ("ok", "")
    monkeypatch.setattr(moderation, "check", check)
    h = await login(client, 6003); ha = await login(client, 6001)
    r = await client.post("/api/jobs", json={"kind": "image", "prompt": "запрет что-то"}, headers=h)
    assert r.status_code == 422
    bal = (await client.get("/api/me", headers=h)).json()["balance"]
    j1 = (await client.post("/api/jobs", json={"kind": "image", "prompt": "звезда кино на пляже"}, headers=h)).json()
    j2 = (await client.post("/api/jobs", json={"kind": "image", "prompt": "звезда эстрады в городе"}, headers=h)).json()
    assert j1["status"] == "review" and (await client.get("/api/me", headers=h)).json()["balance"] == bal - 80
    assert any("На проверке" in t for _, t in no_network if isinstance(t, str))
    q = (await client.get("/api/admin/jobs?status=review", headers=ha)).json()
    assert {x["id"] for x in q} >= {j1["id"], j2["id"]} and q[0]["moderation"] == "известный человек"
    assert (await client.post(f"/api/admin/jobs/{j1['id']}/approve", headers=ha)).json()["status"] == "queued"
    assert (await client.post(f"/api/admin/jobs/{j2['id']}/reject", headers=ha)).json()["status"] == "rejected"
    assert (await client.get("/api/me", headers=h)).json()["balance"] == bal - 40
    assert (await client.post(f"/api/admin/jobs/{j2['id']}/reject", headers=ha)).status_code == 409


@A
async def test_credits_block_prices_promo_log(client, admin):
    h = await login(client, 6004); ha = await login(client, 6001)
    me = (await client.get("/api/me", headers=h)).json()
    u = (await client.get("/api/admin/users?q=6004", headers=ha)).json()[0]
    assert u["id"] == me["id"]
    r = (await client.post(f"/api/admin/users/{u['id']}/credits", json={"delta": 100, "reason": "тест"}, headers=ha)).json()
    assert r["balance"] == me["balance"] + 100
    r = (await client.post(f"/api/admin/users/{u['id']}/credits", json={"delta": -100000, "reason": "обнуление"}, headers=ha)).json()
    assert r["balance"] == 0
    await client.post(f"/api/admin/users/{u['id']}/block", json={"blocked": True}, headers=ha)
    assert (await client.get("/api/me", headers=h)).status_code == 403
    await client.post(f"/api/admin/users/{u['id']}/block", json={"blocked": False}, headers=ha)
    # prices take effect immediately
    p = (await client.get("/api/admin/prices", headers=ha)).json()
    p["price"]["image"] = 55
    p["packs"][0]["stars"] = 350
    assert (await client.put("/api/admin/prices", json={"price": p["price"], "packs": p["packs"]}, headers=ha)).status_code == 200
    assert (await client.get("/api/me/config", headers=h)).json()["price"]["image"] == 55
    assert (await client.get("/api/pay/packs", headers=h)).json()["packs"][0]["stars"] == 350
    assert (await client.put("/api/admin/prices", json={"price": {"image": -1}, "packs": p["packs"]}, headers=ha)).status_code == 422
    from app import pricing
    p2 = (await client.get("/api/admin/prices", headers=ha)).json()["defaults"]
    await client.put("/api/admin/prices", json={"price": p2["price"], "packs": p2["packs"]}, headers=ha)
    # promo
    assert (await client.post("/api/admin/promos", json={"code": "start50", "credits": 50, "max_uses": 1}, headers=ha)).status_code == 200
    r = await client.post("/api/me/promo", json={"code": "START50"}, headers=h)
    assert r.json()["credits"] == 50
    assert (await client.post("/api/me/promo", json={"code": "start50"}, headers=h)).status_code == 409
    h2 = await login(client, 6005)
    assert (await client.post("/api/me/promo", json={"code": "start50"}, headers=h2)).status_code == 410
    assert (await client.post("/api/me/promo", json={"code": "nope"}, headers=h2)).status_code == 404
    lg = (await client.get("/api/admin/log", headers=ha)).json()
    assert {"credits", "block", "unblock", "prices", "promo_add"} <= {x["action"] for x in lg}


@A
async def test_broadcast_preview_and_send(client, admin, monkeypatch, no_network):
    ha = await login(client, 6001)
    assert (await client.post("/api/admin/broadcast/preview", json={"text": "Привет всем", "button": "Открыть"}, headers=ha)).status_code == 200
    from app.routes import admin as am
    jobs = []
    class Pool:
        async def enqueue_job(self, *a, **k): jobs.append(a)
    async def pool(): return Pool()
    monkeypatch.setattr(am, "pool", pool)
    r = (await client.post("/api/admin/broadcast", json={"text": "Новое: голосовой агент", "button": "Попробовать"}, headers=ha)).json()
    assert r["total"] >= 1 and jobs[0][0] == "send_broadcast"
    from app.worker import send_broadcast
    await send_broadcast({}, r["id"])
    b = (await client.get("/api/admin/broadcasts", headers=ha)).json()[0]
    assert b["status"] == "done" and b["sent"] == b["total"]
