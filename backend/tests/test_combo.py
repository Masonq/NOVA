import asyncio, json, shutil, subprocess, tempfile
from pathlib import Path
from test_core import A, login
from test_jobs import _job

TMP = Path(tempfile.mkdtemp())
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=40", "-b:a", "96k", str(TMP / "song.mp3")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=720x1280:rate=24:duration=5", "-pix_fmt", "yuv420p", str(TMP / "live.mp4")], check=True)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return float(d["format"]["duration"]), (v["width"], v["height"]), any(s["codec_type"] == "audio" for s in d["streams"])


def fakes(monkeypatch, kie_calls):
    from app import ai, kie, runner, combo, storage
    from PIL import Image
    import io
    async def image(prompt, aspect="1:1", refs=None, route="picture"):
        b = io.BytesIO(); Image.new("RGB", (576, 1024), (40, 90, 160)).save(b, "PNG"); return b.getvalue()
    async def speech(text, voice=None, instructions=""):
        return ai.pcm_to_wav(b"\x10\x00" * int(24000 * min(4, 0.5 + len(text) / 40)))
    async def create(model, inp):
        kie_calls.append((model, inp)); return f"t{len(kie_calls)}"
    async def wait(task, tick, timeout=0):
        model = dict((f"t{i + 1}", m) for i, (m, _) in enumerate(kie_calls))[task]
        if model.startswith("kling"):
            return {"resultUrls": ["https://x/live.mp4"]}
        return {"data": [{"audio_url": "https://x/song.mp3", "title": "Для Ани", "duration": 40, "id": "sid1"}]}
    async def create_sync(model, inp):
        words = [{"word": "[Припев]\nАня", "startS": 10.0, "endS": 10.6}, {"word": "сегодня", "startS": 10.7, "endS": 11.2},
                 {"word": "твой", "startS": 11.3, "endS": 11.6}, {"word": "день", "startS": 11.7, "endS": 12.4}]
        return {"code": 200, "data": {"code": 200, "data": {"alignedWords": words}}}
    async def download(job, name, url, max_mb=300):
        src = TMP / ("live.mp4" if url.endswith(".mp4") else "song.mp3")
        rel = storage.save_bytes(job, name, src.read_bytes()); return rel
    async def shots(lyrics, style, n): return [{"visual": f"shot {i}", "move": "push in"} for i in range(n)]
    async def brief(name, occasion, about, voices):
        return {"title": "Для Ани", "style": "warm pop", "lyrics": "[Припев]\nАня, сегодня твой день", "card_text": "С днём рождения, Аня!", "card_visual": "card"}
    for mod, k, v in ((ai, "image", image), (ai, "speech", speech), (kie, "create", create), (kie, "wait", wait), (kie, "create_sync", create_sync),
                      (combo, "download", download), (runner, "download", download), (ai, "clip_shots", shots), (ai, "greeting_brief", brief)):
        monkeypatch.setattr(mod, k, v)


@A
async def test_clip_reel_greeting_end_to_end(client, monkeypatch):
    from app import runner
    from app.storage import abs_path
    kie_calls = []
    fakes(monkeypatch, kie_calls)
    # a track to make a clip for
    h, tj = await _job(client, 9401, "music", "песня про Белград", {"instrumental": False})
    await runner.run_job({}, tj)
    assert (await client.get(f"/api/jobs/{tj}", headers=h)).json()["files"][0]["sid"] == "sid1"
    q = lambda kind, prompt, params: client.post("/api/jobs/price", json={"kind": kind, "prompt": prompt, "params": params}, headers=h)
    assert (await q("clip", "Клип", {"track_job": tj})).json()["cost"] == 6 * 12 + 10
    assert (await q("clip", "Клип", {"track_job": tj, "live": True})).json()["cost"] == 4 * (12 + 120) + 10
    # clip, camera moves, synced subtitles
    r = await client.post("/api/jobs", json={"kind": "clip", "prompt": "Клип к треку", "params": {"track_job": tj, "subs": True}}, headers=h)
    cid = r.json()["id"]
    await runner.run_job({}, cid)
    j = (await client.get(f"/api/jobs/{cid}", headers=h)).json()
    assert j["status"] == "done", j.get("error")
    v = next(f for f in j["files"] if f["type"] == "video")
    dur, size, audio = probe(abs_path(v["url"].split("/files/")[1]))
    assert abs(dur - 30) < 1 and size == (1080, 1920) and audio
    ass = next(abs_path(v["url"].split("/files/")[1]).parent.glob("*.ass")).read_text()
    assert "Аня сегодня твой день" in ass and "[Припев]" not in ass and "0:00:00.40" in ass   # chorus at 10 s → clip starts at 9.6 s
    # someone else's track
    h2 = await login(client, 9402)
    assert (await client.post("/api/jobs", json={"kind": "clip", "prompt": "Клип", "params": {"track_job": tj}}, headers=h2)).status_code == 404
    # reel: voice-over, pictures with camera moves, background music, subtitles
    scenes = [{"text": "Белград стоит на слиянии двух рек", "visual": "aerial view of rivers"},
              {"text": "Здесь самая длинная пешеходная улица", "visual": "busy pedestrian street"},
              {"text": "А вечером город оживает", "visual": "city lights at night"}]
    r = await client.post("/api/jobs", json={"kind": "reel", "prompt": "Факты о Белграде",
                                            "params": {"scenes": scenes, "voice": "Puck", "subs": True, "music": True}}, headers=h)
    rid = r.json()["id"]
    await runner.run_job({}, rid)
    j = (await client.get(f"/api/jobs/{rid}", headers=h)).json()
    assert j["status"] == "done", j.get("error")
    v = next(f for f in j["files"] if f["type"] == "video")
    dur, size, audio = probe(abs_path(v["url"].split("/files/")[1]))
    assert 7 < dur < 14 and size == (1080, 1920) and audio
    assert any(m == "ai-music-api/generate" and inp["instrumental"] for m, inp in kie_calls)
    # greeting: song + card + video card (top the test user up first)
    from app.db import Session
    from app.models import User
    from app.credits import grant
    async with Session() as db:
        me = (await client.get("/api/me", headers=h)).json()
        await grant(db, await db.get(User, me["id"]), 500, "promo", "тест"); await db.commit()
    r = await client.post("/api/jobs", json={"kind": "greeting", "prompt": "Любит горы и кофе",
                                            "params": {"name": "Аня", "occasion": "День рождения", "voices": "female"}}, headers=h)
    assert r.status_code == 200, r.text
    gid = r.json()["id"]
    assert r.json()["cost"] == 30 + 30 + 130
    await runner.run_job({}, gid)
    j = (await client.get(f"/api/jobs/{gid}", headers=h)).json()
    assert j["status"] == "done", j.get("error")
    assert {f["type"] for f in j["files"]} >= {"video", "image", "audio"}
    v = next(f for f in j["files"] if f["type"] == "video")
    dur, size, audio = probe(abs_path(v["url"].split("/files/")[1]))
    assert abs(dur - 20) < 1 and audio
    song_inp = next(inp for m, inp in kie_calls if m == "ai-music-api/generate" and not inp["instrumental"] and inp.get("title") == "Для Ани")
    assert song_inp["vocal_gender"] == "f" and "Аня" in song_inp["lyrics"]


@A
async def test_live_scene_failure_falls_back_and_refunds(client, monkeypatch):
    from app import runner, kie
    kie_calls = []
    fakes(monkeypatch, kie_calls)
    h, tj = await _job(client, 9411, "music", "трек", {"instrumental": False})
    await runner.run_job({}, tj)
    from app.db import Session
    from app.models import User
    from app.credits import grant
    async with Session() as db:
        me = (await client.get("/api/me", headers=h)).json()
        await grant(db, await db.get(User, me["id"]), 600, "promo", "тест"); await db.commit()
    orig = kie.wait
    async def wait(task, tick, timeout=0):
        model = dict((f"t{i + 1}", m) for i, (m, _) in enumerate(kie_calls))[task]
        if model.startswith("kling") and task in ("t3",):
            raise kie.KieError("boom")
        return await orig(task, tick, timeout)
    monkeypatch.setattr(kie, "wait", wait)
    bal0 = (await client.get("/api/me", headers=h)).json()["balance"]
    r = await client.post("/api/jobs", json={"kind": "clip", "prompt": "Клип", "params": {"track_job": tj, "live": True}}, headers=h)
    cid = r.json()["id"]
    await runner.run_job({}, cid)
    j = (await client.get(f"/api/jobs/{cid}", headers=h)).json()
    assert j["status"] == "done" and "движением камеры" in (j.get("error") or "")
    assert (await client.get("/api/me", headers=h)).json()["balance"] == bal0 - 538 + 120      # one live scene refunded


@A
async def test_agent_prepares_combos(client, monkeypatch):
    from app import ai, runner
    from app.routes import agent as ag
    from app.db import Session
    from app.models import User
    kie_calls = []
    fakes(monkeypatch, kie_calls)
    async def script(topic, seconds):
        return {"title": "Белград", "music": "lofi", "scenes": [{"text": "Раз два три", "visual": "first shot"}, {"text": "Четыре пять", "visual": "second shot"}]}
    monkeypatch.setattr(ai, "reel_script", script)
    h, tj = await _job(client, 9421, "music", "песня про ночной Белград", {"instrumental": False})
    await runner.run_job({}, tj)
    me = (await client.get("/api/me", headers=h)).json()
    events = []
    async def emit(e): events.append(e)
    async with Session() as db:
        u = await db.get(User, me["id"])
    r = await ag.run_tool("create_media", {"kind": "greeting", "prompt": "любит горы", "name": "Аня", "occasion": "День рождения"}, u, emit)
    assert "190" in r and events[-1]["type"] == "confirm" and events[-1]["cost"] == 190
    r = await ag.run_tool("create_media", {"kind": "greeting", "prompt": "любит горы"}, u, emit)
    assert "имя и повод" in r
    r = await ag.run_tool("create_media", {"kind": "reel", "prompt": "Белград", "seconds": 30}, u, emit)
    assert events[-1]["cost"] == 2 * 12 + 2 + 30 + 10
    r = await ag.run_tool("create_media", {"kind": "clip", "prompt": "клип к последнему треку"}, u, emit)
    assert events[-1]["cost"] == 82 and "Клип" in events[-1]["prompt"]
    r = await ag.run_tool("confirm_pending", {"yes": True}, u, emit)
    assert "Запущено" in r and events[-1]["type"] == "job" and events[-1]["job"]["kind"] == "clip"
