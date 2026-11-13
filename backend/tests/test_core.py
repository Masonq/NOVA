import hashlib, hmac, json, time, os
from datetime import timedelta
from urllib.parse import urlencode
from pathlib import Path
import pytest
from sqlalchemy import select

A = pytest.mark.asyncio(loop_scope="session")
BOT = "123:TEST"


def init_data(uid=1001, name="Макс", age=0, token=BOT, start_param=None):
    d = {"auth_date": str(int(time.time()) - age), "query_id": "q",
         "user": json.dumps({"id": uid, "first_name": name, "username": "max"}, ensure_ascii=False)}
    if start_param:
        d["start_param"] = start_param
    chk = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
    sec = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    d["hash"] = hmac.new(sec, chk.encode(), hashlib.sha256).hexdigest()
    return urlencode(d)


async def login(client, uid=1001):
    r = await client.post("/api/auth/webapp", json={"initData": init_data(uid)})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["token"]}


def test_verify_init_data():
    from app.security import verify_init_data
    assert verify_init_data(init_data(), BOT)["id"] == 1001
    for bad in (init_data(token="999:OTHER"), init_data(age=90000), init_data().replace("hash=", "hash=0")):
        with pytest.raises(ValueError):
            verify_init_data(bad, BOT)


@A
async def test_welcome_pack_once(client):
    h = await login(client, 2001)
    me = (await client.get("/api/me", headers=h)).json()
    assert me["balance"] == 300 and me["name"] == "Макс"
    h = await login(client, 2001)
    assert (await client.get("/api/me", headers=h)).json()["balance"] == 300
    led = (await client.get("/api/me/ledger", headers=h)).json()
    assert [x["kind"] for x in led] == ["welcome"]


@A
async def test_bad_login_and_no_token(client):
    assert (await client.post("/api/auth/webapp", json={"initData": init_data(token="1:x")})).status_code == 401
    assert (await client.get("/api/me")).status_code == 401
    assert (await client.get("/api/me", headers={"Authorization": "Bearer junk"})).status_code == 401


@A
async def test_charge_refund_and_shortage(client):
    from app.db import Session
    from app.models import User
    from app.credits import charge, refund
    await login(client, 3001)
    async with Session() as db:
        u = (await db.execute(select(User).where(User.tg_id == 3001))).scalar_one()
        assert await charge(db, u, 120, "Видео 5 с") == 180
        assert await refund(db, u, 120, "Ошибка генерации") == 300
        await db.commit()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as e:
            await charge(db, u, 301, "много")
        assert e.value.status_code == 402
        await db.rollback()


@A
async def test_site_login_via_bot(client):
    c = (await client.post("/api/auth/code")).json()
    assert c["link"].startswith("https://t.me/NovaAI_Agent?start=login_")
    assert (await client.get(f"/api/auth/code/{c['code']}")).json()["status"] == "waiting"
    upd = {"message": {"text": f"/start login_{c['code']}", "chat": {"type": "private", "id": 4001},
                       "from": {"id": 4001, "first_name": "Аня"}}}
    assert (await client.post("/api/tg/webhook", json=upd)).status_code == 403
    r = await client.post("/api/tg/webhook", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": "wh"})
    assert r.status_code == 200
    p = (await client.get(f"/api/auth/code/{c['code']}")).json()
    assert p["status"] == "ok" and p["user"]["name"] == "Аня" and p["user"]["balance"] == 300
    assert (await client.get(f"/api/auth/code/{c['code']}")).status_code == 410  # one-time


@A
async def test_chat_stream_saves_reply(client, monkeypatch):
    from app.routes import chat as chatmod
    async def fake(models, contents, system):
        assert contents[-1] == {"role": "user", "content": "Привет"}
        for t in ["При", "вет!"]:
            yield t
    monkeypatch.setattr(chatmod, "stream_text", fake)
    h = await login(client, 5001)
    r = await client.post("/api/chat", json={"text": "Привет"}, headers=h)
    events = [json.loads(l[5:]) for l in r.text.splitlines() if l.startswith("data:")]
    assert "".join(e.get("t", "") for e in events) == "Привет!" and events[-1] == {"done": True}
    hist = (await client.get("/api/chat", headers=h)).json()
    assert [(m["role"], m["text"]) for m in hist] == [("user", "Привет"), ("model", "Привет!")]


@A
async def test_chat_model_down(client, monkeypatch):
    from app.routes import chat as chatmod
    from app.ai import AIError as GeminiError
    async def boom(*a):
        raise GeminiError("503")
        yield
    monkeypatch.setattr(chatmod, "stream_text", boom)
    h = await login(client, 5002)
    r = await client.post("/api/chat", json={"text": "Эй"}, headers=h)
    assert "перегружена" in r.text


@A
async def test_expiry_and_reminder(client, monkeypatch):
    from app.db import Session
    from app.models import Job, User, now
    from app import worker, bot
    sent = []
    async def fake_send(chat_id, text, markup=None):
        sent.append((chat_id, text))
    monkeypatch.setattr(bot, "send", fake_send)
    await login(client, 6001)
    sd = Path(os.environ["STORAGE_DIR"])
    async with Session() as db:
        u = (await db.execute(select(User).where(User.tg_id == 6001))).scalar_one()
        old = Job(user_id=u.id, kind="image", status="done", files=[{"path": f"{u.id}/a.png"}], expires_at=now() - timedelta(minutes=1))
        soon = [Job(user_id=u.id, kind="image", status="done", expires_at=now() + timedelta(days=2)) for _ in range(2)]
        db.add_all([old, *soon]); await db.commit()
        (sd / str(u.id)).mkdir(parents=True, exist_ok=True); (sd / f"{u.id}/a.png").write_bytes(b"x")
    assert await worker.cleanup_expired() >= 1
    assert not (sd / f"{u.id}/a.png").exists()
    assert await worker.remind_expiring() == 1
    assert sent and "2 работы" in sent[0][1]
    assert await worker.remind_expiring() == 0  # not twice


@A
async def test_spa_and_cache_headers(client):
    sd = Path(os.environ["STATIC_DIR"]); (sd / "assets").mkdir(exist_ok=True)
    (sd / "index.html").write_text("<html>nova</html>"); (sd / "assets/app-abc.js").write_text("x")
    r = await client.get("/archive")
    assert r.status_code == 200 and "no-store" in r.headers["cache-control"]
    r = await client.get("/assets/app-abc.js")
    assert "immutable" in r.headers["cache-control"]
    assert (await client.get("/../../etc/passwd")).status_code in (200, 404)
    assert (await client.get("/api/nope")).status_code == 404


@A
async def test_delete_account(client):
    h = await login(client, 7001)
    assert (await client.delete("/api/me", headers=h)).json()["ok"]
    assert (await client.get("/api/me", headers=h)).status_code == 401


@A
async def test_speech_wraps_pcm(monkeypatch):
    import httpx
    from app import ai
    class R:
        status_code = 200; content = b"\x00\x00" * 2400; text = ""
    class C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, headers=None, json=None):
            assert url.endswith("/audio/speech") and json["voice"] == "Sulafat" and json["response_format"] == "pcm"
            return R()
    monkeypatch.setattr(httpx, "AsyncClient", C)
    wav = await ai.speech("Привет")
    assert wav[:4] == b"RIFF" and len(wav) > 4000
