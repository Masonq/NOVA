import json
from test_core import login, A
from test_jobs import _job


async def _song(client, monkeypatch, tg, params=None, sent=None):
    from app import runner, kie, storage, ai
    async def brief(prompt, genre="", mood="", vocal=False, voices="auto", seconds=0):
        if sent is not None:
            sent["seconds"] = seconds
        return {"style": "dark trap, 140 bpm", "title": "Ночь", "lyrics": "[Verse 1]\nНочь" if vocal else "", "vocals": "male" if vocal else ""}
    async def create(model, inp):
        if sent is not None:
            sent.update(inp)
        return "task1"
    async def wait(task, tick, timeout):
        return {"data": [{"audio_url": "https://a/1.mp3", "id": "aud1", "title": "Ночь", "duration": 120}]}
    async def dl(job, name, url, max_mb=300): return storage.save_bytes(job, name, b"1")
    monkeypatch.setattr(ai, "music_brief", brief); monkeypatch.setattr(kie, "create", create)
    monkeypatch.setattr(kie, "wait", wait); monkeypatch.setattr(runner, "download", dl)
    h, jid = await _job(client, tg, "music", "трек про ночь", {"instrumental": False, **(params or {})})
    await runner.run_job({}, jid)
    return h, jid


@A
async def test_track_options_reach_suno(client, monkeypatch):
    sent = {}
    h, jid = await _song(client, monkeypatch, 9701, {"length": 60, "avoid": "без гитары, без автотюна", "wild": True}, sent)
    assert sent["model"] == "V6_WILD" and sent["duration"] == 60 and sent["negative_tags"] == "без гитары, без автотюна"
    assert sent["seconds"] == 60
    r = await client.post("/api/jobs", json={"kind": "music", "prompt": "трек", "params": {"length": 45}}, headers=h)
    assert r.status_code == 422


@A
async def test_save_artist_and_sing_with_it(client, monkeypatch):
    from app import kie
    got = {}
    async def persona(inp):
        got.update(inp); return "pers-42"
    monkeypatch.setattr(kie, "create_persona", persona)
    h, jid = await _song(client, monkeypatch, 9702)
    bal = (await client.get("/api/me", headers=h)).json()["balance"]
    r = await client.post("/api/artists", json={"job_id": jid, "name": "Ночной Макс"}, headers=h)
    assert r.status_code == 200, r.text
    a = r.json()
    assert got["task_id"] == "task1" and got["audio_id"] == "aud1" and got["name"] == "Ночной Макс"
    assert a["balance"] == bal - 10
    assert (await client.post("/api/artists", json={"job_id": jid, "name": "Другой"}, headers=h)).status_code == 409
    assert [x["name"] for x in (await client.get("/api/artists", headers=h)).json()] == ["Ночной Макс"]

    sent = {}
    _, jid2 = await _song(client, monkeypatch, 9702, {"artist": a["id"], "voices": "female"}, sent)
    assert sent["persona_id"] == "pers-42" and sent["persona_model"] == "style_persona" and "vocal_gender" not in sent
    j = (await client.get(f"/api/jobs/{jid2}", headers=h)).json()
    assert j["params"]["artist_name"] == "Ночной Макс"

    h2 = await login(client, 9703)                       # someone else's artist is refused
    r = await client.post("/api/jobs", json={"kind": "music", "prompt": "трек", "params": {"artist": a["id"], "instrumental": False}}, headers=h2)
    assert r.status_code == 404
    assert (await client.delete(f"/api/artists/{a['id']}", headers=h2)).status_code == 404
    assert (await client.delete(f"/api/artists/{a['id']}", headers=h)).status_code == 200


@A
async def test_artist_needs_vocals_and_refunds_on_failure(client, monkeypatch):
    from app import kie
    h, jid = await _song(client, monkeypatch, 9704, {"instrumental": True})
    assert (await client.post("/api/artists", json={"job_id": jid, "name": "X"}, headers=h)).status_code == 422
    async def bad(inp):
        raise kie.KieError("500: down")
    monkeypatch.setattr(kie, "create_persona", bad)
    h, jid = await _song(client, monkeypatch, 9705)
    bal = (await client.get("/api/me", headers=h)).json()["balance"]
    r = await client.post("/api/artists", json={"job_id": jid, "name": "X"}, headers=h)
    assert r.status_code == 502
    assert (await client.get("/api/me", headers=h)).json()["balance"] == bal
