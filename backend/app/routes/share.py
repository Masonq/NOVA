"""Public page of a shared work: /s/<token>. Rich preview for Telegram and social networks,
the media itself, and a button that brings the viewer to NOVA through the sharer's referral link."""
import html
import secrets

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import Job, User
from ..security import current_user
from ..storage import public_files

router = APIRouter(tags=["share"])
KIND = {"image": "Картинка", "video": "Видео", "music": "Трек", "tts": "Озвучка"}


@router.post("/api/jobs/{jid}/share")
async def make_link(jid: int, u: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    j = await db.get(Job, jid)
    if not j or j.user_id != u.id or j.status != "done":
        raise HTTPException(404, "Работа не найдена")
    if not j.share_token:
        j.share_token = secrets.token_urlsafe(9)
        await db.commit()
    s = get_settings()
    return {"url": f"{s.public_url}/s/{j.share_token}", "text": f"{KIND[j.kind]} из NOVA: {j.prompt[:80]}"}


PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#0A0A0C">
<title>{title}</title><meta name="description" content="{desc}">
<meta property="og:type" content="{ogtype}"><meta property="og:title" content="{title}"><meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">{ogmedia}<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/icon-192.png"><style>
*{{box-sizing:border-box}}body{{margin:0;min-height:100dvh;background:radial-gradient(120% 60% at 50% 0%,#18122f,#0A0A0C 60%);color:#F2F2F5;
font:15px/1.5 Inter,-apple-system,system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;padding:24px 18px 40px}}
.top{{display:flex;align-items:center;gap:10px;align-self:stretch;max-width:560px;margin:0 auto 18px;font-weight:800;letter-spacing:3px}}
.top img{{width:30px;height:30px;border-radius:9px}}main{{width:100%;max-width:560px;display:flex;flex-direction:column;gap:14px}}
.media{{width:100%;border-radius:22px;overflow:hidden;background:#151518;border:1px solid rgba(255,255,255,.08)}}
.media img,.media video{{display:block;width:100%;max-height:70vh;object-fit:contain;background:#000}}
.aud{{display:flex;gap:14px;align-items:center;padding:14px}}.aud img{{width:84px;height:84px;border-radius:16px;object-fit:cover;flex-shrink:0}}
.pl{{flex:1;min-width:0;display:flex;flex-direction:column;gap:8px}}.pl b{{font-size:15px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.bar{{height:5px;border-radius:3px;background:rgba(255,255,255,.12);cursor:pointer}}.bar i{{display:block;height:100%;width:0;border-radius:3px;background:#fff}}
.tm{{display:flex;justify-content:space-between;font-size:11.5px;color:#8A8A94;font-variant-numeric:tabular-nums}}
.pp{{width:52px;height:52px;border-radius:50%;border:0;background:#fff;display:flex;align-items:center;justify-content:center;flex-shrink:0;cursor:pointer}}
.pp svg{{width:22px;height:22px;fill:#0A0A0C}}
.tag{{align-self:flex-start;display:inline-block;padding:4px 10px;border-radius:9px;background:rgba(255,255,255,.08);font-size:12px;font-weight:600;color:#C8C8D0}}
p{{margin:0;color:#C8C8D0}}a.cta{{display:flex;align-items:center;justify-content:center;height:56px;border-radius:18px;background:#fff;color:#0A0A0C;
font-weight:700;font-size:16px;text-decoration:none;margin-top:6px}}.muted{{color:#8A8A94;font-size:13px;text-align:center}}
.gone{{text-align:center;padding:60px 10px}}</style></head><body>
<div class="top"><img src="/icon-192.png" alt="">NOVA</div><main>{body}
<a class="cta" href="{cta}">Сделать такое же в NOVA</a><p class="muted">Картинки, видео, музыка и&nbsp;озвучка голосом&nbsp;— в&nbsp;Telegram</p></main></body></html>"""


PLAYER_JS = """<script>(function(){const a=document.querySelector('.aud audio'),b=document.querySelector('.pp'),i=document.querySelector('.bar i'),
bar=document.querySelector('.bar'),c=document.querySelector('.tm .c'),d=document.querySelector('.tm .d');
const f=s=>isFinite(s)?Math.floor(s/60)+':'+String(Math.floor(s%60)).padStart(2,'0'):'0:00';
const play='<svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>',pause='<svg viewBox="0 0 24 24"><rect x="6" y="5" width="4" height="14" rx="1.5"/><rect x="14" y="5" width="4" height="14" rx="1.5"/></svg>';
b.onclick=()=>a.paused?a.play():a.pause();a.onplay=()=>{b.innerHTML=pause;b.setAttribute('aria-label','Пауза')};
a.onpause=a.onended=()=>{b.innerHTML=play;b.setAttribute('aria-label','Слушать')};
a.onloadedmetadata=()=>d.textContent=f(a.duration);a.ontimeupdate=()=>{c.textContent=f(a.currentTime);i.style.width=(a.currentTime/a.duration*100||0)+'%'};
bar.onclick=e=>{const r=bar.getBoundingClientRect();if(a.duration)a.currentTime=(e.clientX-r.left)/r.width*a.duration}})()</script>"""


@router.get("/s/{token}", response_class=HTMLResponse)
async def page(token: str, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    j = (await db.execute(select(Job).where(Job.share_token == token))).scalar_one_or_none()
    cta = f"https://t.me/{s.bot_username}?start=ref_{j.user_id}" if j else f"https://t.me/{s.bot_username}"
    if not j or j.status != "done" or not j.files:
        body = '<div class="gone"><h2>Работа больше недоступна</h2><p>Работы хранятся 30 дней. Создайте свою — это пара секунд.</p></div>'
        return HTMLResponse(PAGE.format(title="NOVA", desc="ИИ-агент в Telegram", ogtype="website", url=s.public_url, ogmedia="", body=body, cta=cta), status_code=404)
    e = html.escape
    files = public_files(j)
    track = next((f.get("title") for f in files if f.get("title")), "") if j.kind == "music" else ""
    title = f"«{track}» — трек из NOVA" if track else f"{KIND[j.kind]} из NOVA"
    desc = "Сделано в NOVA — картинки, видео, музыка и озвучка голосом в Telegram"   # the user's prompt stays private
    og, body = "", ""
    if j.kind == "image":
        f = next(x for x in files if x["type"] == "image")
        og = f'<meta property="og:image" content="{e(f["url"])}">'
        body = f'<div class="media"><img src="{e(f["url"])}" alt="Картинка из NOVA"></div>'
    elif j.kind == "video":
        v = next((x for x in files if x["type"] == "video"), None)
        th = next((x for x in files if x["type"] == "thumb"), None)
        og = (f'<meta property="og:image" content="{e(th["url"])}">' if th else "") + (f'<meta property="og:video" content="{e(v["url"])}"><meta property="og:video:type" content="video/mp4">' if v else "")
        body = f'<div class="media"><video src="{e(v["url"])}" {"poster=" + chr(34) + e(th["url"]) + chr(34) if th else ""} controls playsinline loop></video></div>'
    else:
        a = next((x for x in files if x["type"] == "audio"), files[0])
        cover = a.get("cover_url")
        og = (f'<meta property="og:image" content="{e(cover)}">' if cover else "") + f'<meta property="og:audio" content="{e(a["url"])}">'
        name = e(a.get("title") or ("Трек" if j.kind == "music" else "Озвучка"))
        body = (f'<div class="media aud">{f"<img src={chr(34)}{e(cover)}{chr(34)} alt={chr(34)}{chr(34)}>" if cover else ""}'
                f'<div class="pl"><b>{name}</b><div class="bar"><i></i></div><div class="tm"><span class="c">0:00</span><span class="d"></span></div></div>'
                f'<button class="pp" aria-label="Слушать"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></button>'
                f'<audio src="{e(a["url"])}" preload="metadata"></audio></div>{PLAYER_JS}')
    return HTMLResponse(PAGE.format(title=e(title), desc=e(desc), ogtype="video.other" if j.kind == "video" else "website",
                                    url=e(f"{s.public_url}/s/{token}"), ogmedia=og, body=body, cta=e(cta)))
