"""Finished works are sent to the user's chat with the bot (Bot API 10.4):
a picture as a photo, a video as a playable video, a track or a voice-over as a widget card in the style of the NOVA player.
Widgets have no network and no audio, so the card's ▶ asks the bot, and the bot sends the track below it to play natively."""
import base64
import io
import logging
import zlib

from . import bot
from .config import get_settings
from .models import Job, User
from .storage import abs_path

log = logging.getLogger("nova.deliver")
ICON = {"image": "🖼", "video": "🎬", "music": "🎵", "tts": "🎙"}
VOCALS = {"male": "мужской вокал", "female": "женский вокал", "duet": "дуэт"}


def _markup(j: Job) -> dict:
    return bot.open_app_markup("Открыть в NOVA", f"#/archive?job={j.id}")


def _caption(j: Job) -> str:
    p = j.params or {}
    title = next((f.get("title") for f in j.files or [] if f.get("title")), "") or j.prompt
    return f"{ICON.get(j.kind, '✨')} {title[:180]}"


def _mmss(sec) -> str:
    sec = int(float(sec or 0))
    return f"{sec // 60}:{sec % 60:02d}"


def _cover_data(rel: str | None, size: int) -> str:
    if not rel:
        return ""
    try:
        from PIL import Image
        with Image.open(abs_path(rel)) as im:
            im = im.convert("RGB")
            im.thumbnail((size, size))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=55, optimize=True)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def player_html(j: Job, f: dict) -> str:
    """The NOVA player as a widget, kept under 4 KB after zlib, as Telegram counts it."""
    title = (f.get("title") or j.prompt or "Трек").replace("<", "‹")[:60]
    p = j.params or {}
    if j.kind == "tts":
        sub = " · ".join(x for x in ("Озвучка", p.get("voice"), p.get("tone")) if x)
    else:
        sub = " · ".join(x for x in (p.get("genre"), VOCALS.get((p.get("brief") or {}).get("vocals"), "")) if x) or "Трек"
    sub = sub.replace("<", "‹")[:60]
    for size in (64, 48, 0):
        cover = _cover_data(f.get("cover_thumb") or f.get("cover"), size) if size else ""
        img = f'<img src="{cover}">' if cover else '<div class="ph">♪</div>'
        html = (
            "<style>body{margin:0;padding:12px 12px max(10px,env(safe-area-inset-bottom));background:#141418;color:#f2f2f5;font:14px system-ui}"
            ".r{display:flex;align-items:center;gap:12px}img,.ph{width:56px;height:56px;border-radius:13px;object-fit:cover;flex-shrink:0}"
            ".ph{background:#23232a;display:flex;align-items:center;justify-content:center;font-size:24px;color:#8a8a94}"
            ".t{flex:1;min-width:0}b{display:block;font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}"
            "small{color:#8a8a94;font-size:12px}.w{display:flex;align-items:center;gap:2px;height:22px;margin-top:7px}"
            ".w i{flex:1;border-radius:2px;background:#3a3a44}.on .w i{background:#7fb2ff}"
            "button{width:48px;height:48px;border-radius:50%;border:0;background:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0;padding:0}"
            "button svg{width:20px;height:20px;fill:#0a0a0c}.f{display:flex;justify-content:space-between;color:#8a8a94;font-size:11.5px;margin-top:6px}</style>"
            f'<div class="r" id="r">{img}<div class="t"><b>{title}</b><small>{sub}</small><div class="w" id="w"></div></div>'
            '<button id="p"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></button></div>'
            f'<div class="f"><span id="s">Нажмите ▶ — трек придёт ниже</span><span>{_mmss(f.get("duration"))}</span></div>'
            "<script>const W=TelegramWidget,w=document.getElementById('w'),s=document.getElementById('s'),b=document.getElementById('p');"
            f"let x={j.id % 97 + 7};for(let i=0;i<28;i++){{x=(x*73+19)%101;const e=document.createElement('i');e.style.height=(25+x*.7)+'%';w.appendChild(e)}}"
            "function d(){let c={};try{c=JSON.parse(W.chatData)||{}}catch(e){}if(c.s){document.getElementById('r').className='r on';s.textContent='Трек ниже ↓'}}"
            "W.onEvent('chatDataChanged',d);d();"
            f"b.onclick=()=>{{s.textContent='Отправляю…';W.request('play:{j.id}').then(()=>{{s.textContent='Трек ниже ↓';document.getElementById('r').className='r on'}},"
            "e=>{s.textContent=e.code==='RATE_LIMITED'?'Подождите пару секунд':'Не получилось — откройте в NOVA'})}</script>"
        )
        if len(zlib.compress(html.encode(), 9)) <= 4000:
            return html
    return html


async def send_audio(chat_id: int, j: Job, f: dict, reply_to: int | None = None) -> dict:
    files = {"audio": (f"{(f.get('title') or 'track')[:40]}.mp3", open(abs_path(f["path"]), "rb"), "audio/mpeg")}
    if f.get("cover"):
        try:
            from PIL import Image
            with Image.open(abs_path(f["cover"])) as im:
                im = im.convert("RGB"); im.thumbnail((320, 320))
                buf = io.BytesIO(); im.save(buf, "JPEG", quality=80)
            files["thumbnail"] = ("cover.jpg", buf.getvalue(), "image/jpeg")
        except Exception:
            pass
    data = {"chat_id": chat_id, "title": (f.get("title") or j.prompt)[:60], "performer": "NOVA",
            "duration": int(float(f.get("duration") or 0)) or None, "reply_markup": _markup(j)}
    if reply_to:
        data["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    return await bot.call_files("sendAudio", data, files)


async def deliver(j: Job, u: User) -> None:
    """Sends a finished work to the user's chat with the bot. Never breaks the job."""
    if not u or not u.can_message or not u.tg_id or j.status != "done":
        return
    try:
        files = j.files or []
        if j.kind == "image":
            f = next((x for x in files if x.get("type") == "image"), None)
            if not f:
                return
            path = abs_path(f["path"])
            method, field = ("sendPhoto", "photo") if path.stat().st_size <= 9_500_000 else ("sendDocument", "document")
            d = await bot.call_files(method, {"chat_id": u.tg_id, "caption": _caption(j), "reply_markup": _markup(j)},
                                     {field: (path.name, open(path, "rb"), "image/png")})
            if not d.get("ok") and method == "sendPhoto":      # Telegram refuses some sizes as a photo: send the file
                await bot.call_files("sendDocument", {"chat_id": u.tg_id, "caption": _caption(j), "reply_markup": _markup(j)},
                                     {"document": (path.name, open(path, "rb"), "image/png")})
        elif j.kind == "video":
            f = next((x for x in files if x.get("type") == "video"), None)
            if not f:
                return
            th = next((x for x in files if x.get("type") == "thumb"), None)
            up = {"video": ("nova.mp4", open(abs_path(f["path"]), "rb"), "video/mp4")}
            if th:
                up["thumbnail"] = ("thumb.jpg", open(abs_path(th["path"]), "rb"), "image/jpeg")
            await bot.call_files("sendVideo", {"chat_id": u.tg_id, "caption": _caption(j), "supports_streaming": True,
                                               "reply_markup": _markup(j)}, up)
        elif j.kind in ("music", "tts"):
            f = next((x for x in files if x.get("type") == "audio"), None)
            if not f:
                return
            d = await bot.call("sendWidget", {"chat_id": u.tg_id, "html": player_html(j, f), "caption": _caption(j),
                                              "allow_queries": True, "height": 0, "reply_markup": _markup(j)})
            if not d.get("ok"):                                 # no widgets (old API or client): the track itself
                await send_audio(u.tg_id, j, f)
    except Exception as e:
        log.warning("deliver %s failed: %s", j.id, e)


async def on_widget_query(q: dict, db) -> None:
    """▶ on the player card: send the track below it, mark the card, answer the widget."""
    from sqlalchemy import select
    data = q.get("data") or ""
    ans = "no"
    try:
        if data.startswith("play:") and data[5:].isdigit():
            j = await db.get(Job, int(data[5:]))
            u = await db.get(User, j.user_id) if j else None
            if j and u and u.tg_id == (q.get("from") or {}).get("id") and j.status == "done":
                f = next((x for x in j.files or [] if x.get("type") == "audio"), None)
                if f:
                    d = await send_audio(u.tg_id, j, f, q.get("message_id"))
                    ans = "ok" if d.get("ok") else "fail"
                    if d.get("ok") and q.get("message_id"):
                        await bot.call("editMessageWidgetData", {"chat_id": u.tg_id, "message_id": q["message_id"], "chat_data": '{"s":1}'})
    finally:
        await bot.call("answerWidgetQuery", {"widget_query_id": q["id"], "data": ans})
