import asyncio, json, os
from pathlib import Path
import pytest
from sqlalchemy import select
from test_core import login, A

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


@pytest.fixture
def queued(monkeypatch):
    got = []
    async def fake(jid): got.append(jid)
    from app.routes import jobs as jm
    monkeypatch.setattr(jm, "enqueue", fake)
    return got


async def balance(client, h):
    return (await client.get("/api/me", headers=h)).json()["balance"]


@A
async def test_create_charges_and_queues(client, queued):
    h = await login(client, 8001)
    r = await client.post("/api/jobs", json={"kind": "image", "prompt": "лиса логотип", "params": {"style": "Логотип", "aspect": "1:1"}}, headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["cost"] == 40 and j["status"] == "queued" and queued == [j["id"]]
    assert await balance(client, h) == 260
    q = (await client.post("/api/jobs/price", json={"kind": "video", "prompt": "город", "params": {"duration": 10, "quality": "1080p", "sound": True}}, headers=h)).json()
    assert q["cost"] == 540


@A
async def test_validation_and_limits(client, queued):
    h = await login(client, 8002)
    bad = await client.post("/api/jobs", json={"kind": "video", "prompt": "x y", "params": {"duration": 7}}, headers=h)
    assert bad.status_code == 422
    big = await client.post("/api/jobs", json={"kind": "video", "prompt": "дорогое видео", "params": {"duration": 15, "quality": "1080p", "sound": True}}, headers=h)
    assert big.status_code == 402 and "Не хватает" in big.json()["detail"]
    for _ in range(3):
        assert (await client.post("/api/jobs", json={"kind": "tts", "prompt": "Привет мир"}, headers=h)).status_code == 200
    r = await client.post("/api/jobs", json={"kind": "tts", "prompt": "Ещё раз"}, headers=h)
    assert r.status_code == 429
    act = (await client.get("/api/jobs/active", headers=h)).json()
    assert len(act) == 3
    c = await client.post(f"/api/jobs/{act[0]['id']}/cancel", headers=h)
    assert c.json()["status"] == "cancelled"
    assert await balance(client, h) == 300 - 2 * 2


async def _job(client, uid, kind, prompt, params=None):
    from app.routes import jobs as jm
    async def nop(jid): pass
    jm.enqueue = nop
    h = await login(client, uid)
    r = await client.post("/api/jobs", json={"kind": kind, "prompt": prompt, "params": params or {}}, headers=h)
    assert r.status_code == 200, r.text
    return h, r.json()["id"]


@A
async def test_image_partial_refund(client, monkeypatch):
    from app import runner, ai
    calls = {"n": 0}
    async def fake_image(prompt, aspect, refs, quality="fast"):
        calls["n"] += 1
        assert "logo" in prompt
        if calls["n"] == 2:
            raise ai.AIError("boom")
        return PNG
    monkeypatch.setattr(ai, "image", fake_image)
    h, jid = await _job(client, 8101, "image", "лиса", {"style": "Логотип"})
    await runner.run_job({}, jid)
    j = (await client.get(f"/api/jobs/{jid}", headers=h)).json()
    assert j["status"] == "done" and len(j["files"]) == 3 and j["expires"]
    assert all(f["url"].startswith("https://nova.test/files/") for f in j["files"])
    assert await balance(client, h) == 300 - 40 + 10


@A
async def test_video_flow_and_failure_refund(client, monkeypatch):
    from app import runner, kie, storage
    seen = {}
    async def create(model, inp):
        seen.update(model=model, inp=inp); return "t1"
    async def wait(task, tick, timeout):
        await tick("generating", 30); return {"resultUrls": ["https://cdn/x.mp4"]}
    async def dl(job, name, url, max_mb=300):
        return storage.save_bytes(job, name, b"\x00" * 10)
    monkeypatch.setattr(kie, "create", create); monkeypatch.setattr(kie, "wait", wait)
    monkeypatch.setattr(runner, "download", dl)
    h, jid = await _job(client, 8201, "video", "неоновый город", {"duration": 5, "quality": "720p", "sound": False})
    await runner.run_job({}, jid)
    j = (await client.get(f"/api/jobs/{jid}", headers=h)).json()
    assert j["status"] == "done" and j["files"][0]["type"] == "video"
    assert seen["model"] == "kling-3.0/video" and seen["inp"]["mode"] == "std" and seen["inp"]["duration"] == "5" and seen["inp"]["aspect_ratio"] == "9:16"
    async def bad_wait(task, tick, timeout): raise kie.KieError("fail")
    monkeypatch.setattr(kie, "wait", bad_wait)
    _, jid2 = await _job(client, 8201, "video", "ещё видео", {"duration": 5})
    await runner.run_job({}, jid2)
    j2 = (await client.get(f"/api/jobs/{jid2}", headers=h)).json()
    assert j2["status"] == "failed"
    assert await balance(client, h) == 300 - 120
    led = (await client.get("/api/me/ledger", headers=h)).json()
    assert led[0]["kind"] == "refund" and led[0]["delta"] == 120


@A
async def test_music_and_tts(client, monkeypatch):
    from app import runner, kie, storage, ai
    async def create(model, inp):
        assert model == "ai-music-api/generate" and inp["model"] == "V6" and inp["instrumental"] is False and inp["style"] == "Lo-fi"
        return "m1"
    async def wait(task, tick, timeout):
        return {"data": [{"audio_url": "https://a/1.mp3", "image_url": "https://a/1.jpg", "title": "Night", "duration": 134},
                         {"audio_url": "https://a/2.mp3", "title": "Night 2"}]}
    async def dl(job, name, url, max_mb=300): return storage.save_bytes(job, name, b"1")
    monkeypatch.setattr(kie, "create", create); monkeypatch.setattr(kie, "wait", wait); monkeypatch.setattr(runner, "download", dl)
    h, jid = await _job(client, 8301, "music", "бит для работы", {"genre": "Lo-fi", "instrumental": False})
    await runner.run_job({}, jid)
    f = (await client.get(f"/api/jobs/{jid}", headers=h)).json()["files"]
    assert len(f) == 2 and f[0]["title"] == "Night" and f[0]["cover"].endswith("cover1.jpg")
    async def speech(text, voice=None, instructions=""):
        assert voice == "Puck" and "шёпот" in instructions.lower()
        return ai.pcm_to_wav(b"\x00\x00" * 24000)
    monkeypatch.setattr(ai, "speech", speech)
    _, jid2 = await _job(client, 8301, "tts", "Привет, это проверка", {"voice": "Puck", "tone": "Шёпот"})
    await runner.run_job({}, jid2)
    t = (await client.get(f"/api/jobs/{jid2}", headers=h)).json()
    assert t["status"] == "done" and t["files"][0]["url"].endswith((".mp3", ".wav"))


@A
async def test_upload_only_images(client):
    h = await login(client, 8401)
    r = await client.post("/api/uploads", files={"file": ("a.png", PNG, "image/png")}, headers=h)
    assert r.status_code == 200 and r.json()["url"].endswith(".png")
    r = await client.post("/api/uploads", files={"file": ("a.txt", b"hello", "text/plain")}, headers=h)
    assert r.status_code == 415



@A
async def test_image_model_per_task_and_enhanced_prompt(client, monkeypatch):
    from app import runner, ai, storage
    seen = []
    async def enhance(prompt, style="", has_ref=False):
        return "A detailed prompt: " + prompt
    async def fake_image(prompt, aspect, refs, route="picture"):
        seen.append((route, aspect, prompt)); return PNG
    monkeypatch.setattr(ai, "enhance_prompt", enhance)
    monkeypatch.setattr(ai, "image", fake_image)
    h, j1 = await _job(client, 8601, "image", "лиса в неоне", {"style": "Фото", "aspect": "3:4"})
    _, j2 = await _job(client, 8601, "image", "логотип «Зерно»", {"style": "Логотип"})
    up = (await client.post("/api/uploads", files={"file": ("a.png", PNG, "image/png")}, headers=h)).json()["url"]
    _, j3 = await _job(client, 8601, "image", "сделай меня в костюме", {"style": "Арт", "refs": [up]})
    for j in (j1, j2, j3):
        await runner.run_job({}, j)
    routes = {}
    for r, a, p in seen:
        routes.setdefault(r, set()).add(p)
    assert set(routes) == {"picture", "logo", "edit"} and all(len(v) == 1 for v in routes.values())
    j = (await client.get(f"/api/jobs/{j1}", headers=h)).json()
    assert j["status"] == "done" and j["cost"] == 40 and j["params"]["model"] == "bytedance-seed/seedream-5-5"
    assert j["params"]["enhanced"].startswith("A detailed prompt")
    assert (await client.get(f"/api/jobs/{j2}", headers=h)).json()["params"]["model"] == "openai/gpt-image-2.6-flare"
    assert (await client.get(f"/api/jobs/{j3}", headers=h)).json()["params"]["model"] == "google/gemini-nano-banana-2.1"
