import base64, json
import pytest
from test_core import login, A
from app import ai
from app.routes import agent as ag


def wav_b64(sec=1.5):
    return base64.b64encode(ai.pcm_to_wav(b"\x00\x00" * int(16000 * sec), 16000)).decode()


def events(text):
    return [json.loads(l[5:]) for l in text.splitlines() if l.startswith("data:")]


@pytest.fixture
def env(monkeypatch):
    store = {}
    class P:
        async def set(self, uid, d): store[uid] = d
        async def pop(self, uid): return store.pop(uid, None)
    monkeypatch.setattr(ag, "pending", P())
    async def speech(text, voice=None, instructions=""):
        return ai.pcm_to_wav(b"\x00\x00" * 24000 * 3)          # 3 s per sentence
    monkeypatch.setattr(ai, "speech", speech)
    from app.routes import jobs as jm
    q = []
    async def enq(jid): q.append(jid)
    monkeypatch.setattr(jm, "enqueue", enq)
    script = []
    async def stream(model, msgs, tools=None, timeout=90):
        rnd = script.pop(0)
        for item in rnd:
            yield item
    monkeypatch.setattr(ai, "stream_events", stream)
    return {"script": script, "queue": q, "store": store}


def test_split_ready():
    out, rest = ag.split_ready("Привет! Как дела? Сейчас", True)
    assert out == ["Привет!", "Как дела?"] and rest == "Сейчас"
    out, rest = ag.split_ready("Отличный вопрос, давай разберёмся подробно, потому что тут есть нюансы и детали", True)
    assert len(out) == 1 and out[0].endswith(",")


@A
async def test_voice_turn_confirm_and_launch(client, env):
    h = await login(client, 9501)
    env["script"] += [
        [("text", "[[Сделай логотип кофейни]] Секунду. "), ("tools", [{"id": "c1", "name": "create_media", "arguments": json.dumps({"kind": "image", "prompt": "Логотип кофейни", "style": "Логотип"})}])],
        [("text", "Это будет стоить 12 кредитов. Запускаем?")],
    ]
    r = await client.post("/api/agent/turn", json={"audio": wav_b64()}, headers=h)
    ev = events(r.text)
    types = [e["type"] for e in ev]
    assert types[0] == "heard" and ev[0]["text"] == "Сделай логотип кофейни"
    assert "confirm" in types and next(e for e in ev if e["type"] == "confirm")["cost"] == 12
    auds = [e for e in ev if e["type"] == "audio"]
    assert [a["seq"] for a in auds] == sorted(a["seq"] for a in auds) and len(auds) == 3
    done = ev[-1]
    assert done["type"] == "done" and done["cost"] == 1 and done["balance"] == 299   # 1.5 s in + 9 s out -> 1 credit
    assert env["store"][(await client.get("/api/me", headers=h)).json()["id"]]["kind"] == "image"

    env["script"] += [
        [("tools", [{"id": "c2", "name": "confirm_pending", "arguments": json.dumps({"yes": True})}])],
        [("text", "Запустила! Пришлю, когда будет готово.")],
    ]
    r = await client.post("/api/agent/turn", json={"text": "да"}, headers=h)
    ev = events(r.text)
    job = next(e for e in ev if e["type"] == "job")
    assert job["job"]["kind"] == "image" and job["job"]["cost"] == 12 and env["queue"] == [job["job"]["id"]]
    assert ev[-1]["balance"] == 299 - 12 - 1
    hist = (await client.get("/api/chat", headers=h)).json()
    assert hist == []                                   # agent talk is not mixed into the text chat


@A
async def test_archive_search_and_memory(client, env):
    h = await login(client, 9502)
    env["script"] += [
        [("text", "[[]]"), ("tools", [{"id": "a", "name": "remember", "arguments": json.dumps({"fact": "Любит lo-fi"})}])],
        [("text", "Не расслышала, повторите, пожалуйста.")],
    ]
    ev = events((await client.post("/api/agent/turn", json={"audio": wav_b64()}, headers=h)).text)
    assert ev[0] == {"type": "heard", "text": ""} and any(e["type"] == "memory" for e in ev)
    mem = (await client.get("/api/me/memory", headers=h)).json()
    assert mem and mem[0]["text"] == "Любит lo-fi"
    env["script"] += [[("tools", [{"id": "s", "name": "search_archive", "arguments": json.dumps({"query": "трек про дорогу"})}])],
                      [("text", "Ничего не нашла.")]]
    ev = events((await client.post("/api/agent/turn", json={"text": "найди трек про дорогу"}, headers=h)).text)
    assert not any(e["type"] == "cards" for e in ev) and ev[-1]["type"] == "done"


@A
async def test_settings_and_empty_balance(client, env):
    h = await login(client, 9503)
    assert (await client.put("/api/agent/settings", json={"voice": "Puck"}, headers=h)).json()["voice"] == "Puck"
    assert (await client.put("/api/agent/settings", json={"voice": "Nope"}, headers=h)).status_code == 422
    assert (await client.get("/api/agent/settings", headers=h)).json()["voice"] == "Puck"
    from app.db import Session
    from app.models import User
    from sqlalchemy import update
    async with Session() as db:
        await db.execute(update(User).where(User.tg_id == 9503).values(balance=0)); await db.commit()
    r = await client.post("/api/agent/turn", json={"text": "привет"}, headers=h)
    assert r.status_code == 402


@A
async def test_failed_sentence_leaves_no_gap(client, env, monkeypatch):
    calls = []
    async def speech(text, voice=None, instructions=""):
        calls.append(text)
        if "Второе" in text:
            raise ai.AIError("озвучка: 429 rate limited")
        return ai.pcm_to_wav(b"\x00\x00" * 24000)
    monkeypatch.setattr(ai, "speech", speech)
    h = await login(client, 9551)
    env["script"] += [[("text", "[[Расскажи]] Первое предложение здесь. Второе предложение тоже здесь. Третье предложение в конце.")]]
    ev = events((await client.post("/api/agent/turn", json={"audio": wav_b64()}, headers=h)).text)
    auds = [e for e in ev if e["type"] == "audio"]
    assert len(calls) == 3 and [a["seq"] for a in auds] == [0, 1] and auds[1]["text"].startswith("Третье")


@A
async def test_speech_survives_rate_limits(monkeypatch):
    import httpx
    tries = []
    class R:
        def __init__(self, code, content=b""): self.status_code, self.content, self.text, self.headers = code, content, "busy", {}
    class C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass
        async def post(self, url, headers=None, json=None):
            tries.append(1)
            return R(429) if len(tries) < 3 else R(200, b"\x00\x00" * 100)
    monkeypatch.setattr(httpx, "AsyncClient", C)
    sleeps = []
    async def nosleep(s): sleeps.append(s)
    monkeypatch.setattr(ai.asyncio, "sleep", nosleep)
    wav = await ai.speech("Привет", "Sulafat")
    assert wav[:4] == b"RIFF" and len(tries) == 3 and len(sleeps) == 2 and sleeps[1] > sleeps[0]
