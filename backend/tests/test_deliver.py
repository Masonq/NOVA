import io
from test_core import login, A
from test_jobs import _job, PNG
from app.config import get_settings


@A
async def test_finished_works_are_sent_to_the_chat(client, monkeypatch):
    from app import bot, runner, ai, kie, storage
    calls = []
    async def call(method, payload):
        calls.append((method, payload)); return {"ok": method != "sendWidget" or not calls_fail.get("w")}
    async def call_files(method, data, files):
        calls.append((method, {**data, "_files": sorted(files)})); return {"ok": True}
    calls_fail = {}
    monkeypatch.setattr(bot, "call", call); monkeypatch.setattr(bot, "call_files", call_files)
    async def img(prompt, aspect, refs, route="picture"): return PNG
    monkeypatch.setattr(ai, "image", img)
    h, jid = await _job(client, 9201, "image", "закат над Савой", {})
    await runner.run_job({}, jid)
    photo = [c for c in calls if c[0] == "sendPhoto"]
    assert photo and photo[0][1]["_files"] == ["photo"] and photo[0][1]["caption"].startswith("🖼")
    assert "web_app" in str(photo[0][1]["reply_markup"])
    # a track: the player widget
    async def create(model, inp): return "t"
    async def wait(task, tick, timeout): return {"data": [{"audio_url": "https://a/1.mp3", "title": "Holy Malibu", "duration": 154}]}
    async def dl(job, name, url, max_mb=300): return storage.save_bytes(job, name, b"ID3")
    monkeypatch.setattr(kie, "create", create); monkeypatch.setattr(kie, "wait", wait); monkeypatch.setattr(runner, "download", dl)
    calls.clear()
    _, mid = await _job(client, 9201, "music", "трек про ночь", {"instrumental": False})
    await runner.run_job({}, mid)
    w = [c for c in calls if c[0] == "sendWidget"]
    assert w and w[0][1]["allow_queries"] is True and f"play:{mid}" in w[0][1]["html"] and "Holy Malibu" in w[0][1]["html"]
    assert not [c for c in calls if c[0] == "sendAudio"]
    # an old client / API without widgets: the track itself
    calls.clear(); calls_fail["w"] = True
    _, mid2 = await _job(client, 9201, "music", "ещё трек", {"instrumental": False})
    await runner.run_job({}, mid2)
    assert [c for c in calls if c[0] == "sendAudio"]
    # ▶ on the card: the track goes below it, the card is marked, the widget gets an answer
    calls.clear(); calls_fail.clear()
    me = (await client.get("/api/me", headers=h)).json()
    async def tg_id():
        from app.db import Session
        from app.models import User
        async with Session() as db:
            return (await db.get(User, me["id"])).tg_id
    tid = await tg_id()
    hook = lambda upd: client.post("/api/tg/webhook", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": get_settings().webhook_secret})
    await hook({"update_id": 7, "widget_query": {"id": "q1", "from": {"id": tid}, "chat": {"id": tid, "type": "private"}, "message_id": 55, "data": f"play:{mid}"}})
    names = [c[0] for c in calls]
    assert names == ["sendAudio", "editMessageWidgetData", "answerWidgetQuery"]
    assert calls[0][1]["reply_parameters"]["message_id"] == 55 and calls[2][1]["data"] == "ok"
    # someone else's track: nothing is sent, the widget still gets an answer
    calls.clear()
    await hook({"update_id": 8, "widget_query": {"id": "q2", "from": {"id": 424242}, "message_id": 56, "data": f"play:{mid}"}})
    assert [c[0] for c in calls] == ["answerWidgetQuery"] and calls[0][1]["data"] == "no"


def test_player_widget_fits_telegram_limit():
    import types, zlib
    from app.deliver import player_html
    j = types.SimpleNamespace(id=5, kind="tts", prompt="Привет! " * 40, params={"voice": "Sulafat", "tone": "Бодро"})
    h = player_html(j, {"title": "", "duration": 12})
    assert len(zlib.compress(h.encode(), 9)) <= 4096 and len(h.encode()) <= 32768 and "Озвучка" in h
