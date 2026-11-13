from test_core import A, login
from test_jobs import _job, PNG

TEXT = """[Куплет 1: мужской]
Может, слить ей на кисть holy Malibu
Я прошу: не влюбись — лямы на кону

[Предприпев : Женский]
Привет, милый, что с твоим голосом?
Дела все сделала, уложила волосы

[Припев: дуэт]
Строка один
Строка два"""


def test_parse_sections():
    from app.ai import parse_sections, suno_lyrics
    s = parse_sections(TEXT)
    assert [(x["label"], x["who"]) for x in s] == [("Куплет 1", "male"), ("Предприпев", "female"), ("Припев", "duet")]
    assert s[0]["text"].startswith("Может") and "[" not in s[1]["text"]
    lyr = suno_lyrics(s)
    assert "[Куплет 1: Male Vocal]" in lyr and "[Предприпев: Female Vocal]" in lyr and "[Припев: Male & Female Vocals]" in lyr
    assert parse_sections("Обычный текст без разметки") == []


@A
async def test_voice_over_by_parts(client, monkeypatch):
    from app import ai, runner
    reads = []
    async def speech(text, voice=None, instructions=""):
        reads.append((voice, text.splitlines()[0])); return ai.pcm_to_wav(b"\x00\x00" * 2400)
    monkeypatch.setattr(ai, "speech", speech)
    h = await login(client, 9301)
    q = await client.post("/api/jobs/price", json={"kind": "tts", "prompt": TEXT, "params": {}}, headers=h)
    assert q.json()["cost"] == 2                               # tags are not counted
    r = await client.post("/api/jobs", json={"kind": "tts", "prompt": TEXT, "params": {"voice": "Kore", "male": "Puck", "female": "Leda"}}, headers=h)
    jid = r.json()["id"]
    await runner.run_job({}, jid)
    j = (await client.get(f"/api/jobs/{jid}", headers=h)).json()
    assert j["status"] == "done" and j["params"]["male"] == "Puck" and j["params"]["female"] == "Leda"
    assert [v for v, _ in reads] == ["Puck", "Leda", "Puck", "Leda"]   # verse male, pre-chorus female, duet lines in turns
    assert reads[0][1].startswith("Может")
    bad = await client.post("/api/jobs", json={"kind": "tts", "prompt": TEXT, "params": {"male": "Leda"}}, headers=h)
    assert "male" not in (await client.get(f"/api/jobs/{bad.json()['id']}", headers=h)).json()["params"]   # a female voice can't be the male one


@A
async def test_music_sings_users_own_marked_lyrics(client, monkeypatch):
    from app import runner, kie, storage
    sent = {}
    async def create(model, inp):
        sent.update(inp); return "t"
    async def wait(task, tick, timeout):
        return {"data": [{"audio_url": "https://a/1.mp3"}]}
    async def dl(job, name, url, max_mb=300): return storage.save_bytes(job, name, b"1")
    monkeypatch.setattr(kie, "create", create); monkeypatch.setattr(kie, "wait", wait); monkeypatch.setattr(runner, "download", dl)
    h, jid = await _job(client, 9302, "music", TEXT, {"instrumental": False, "genre": "Рэп"})
    await runner.run_job({}, jid)
    assert "[Куплет 1: Male Vocal]" in sent["lyrics"] and "Может, слить ей на кисть holy Malibu" in sent["lyrics"]
    assert "vocal_gender" not in sent                          # two genders: no single-voice nudge
