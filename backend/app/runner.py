"""Executes generation jobs in the worker. Each job: progress + stage in the DB, files in storage,
credits refunded automatically when something fails."""
import asyncio
import logging
import time
from datetime import timedelta

from . import ai, bot, kie
from .config import get_settings
from .credits import refund
from .db import Session
from .models import Job, User, now
from .storage import abs_path, download, ffmpeg, make_thumb, save_bytes

log = logging.getLogger("nova.runner")

STYLE_HINT = {
    "Фото": "photorealistic photo, natural light, high detail",
    "Арт": "digital art illustration, expressive, rich colors",
    "Логотип": "clean minimalist vector logo, flat, centered on a plain background, no mockup, crisp edges",
    "3D": "3D render, soft studio lighting, high detail",
    "Аниме": "anime style illustration, clean lineart",
}
RU_STAGE = {"waiting": "В очереди", "queuing": "В очереди", "generating": "Рисую кадры", "success": "Сборка"}


async def _update(job_id: int, **kw):
    async with Session() as db:
        j = await db.get(Job, job_id)
        if j is None:
            return None
        for k, v in kw.items():
            setattr(j, k, v)
        await db.commit()
        return j


async def _finish(job_id: int, files: list, refund_part: int = 0, note: str = ""):
    s = get_settings()
    async with Session() as db:
        j = await db.get(Job, job_id)
        j.status, j.files, j.progress, j.stage = "done", files, 100, "Готово"
        j.finished_at = now()
        j.expires_at = now() + timedelta(days=s.keep_days)
        if note:
            j.error = note
        u = await db.get(User, j.user_id)
        if refund_part and u:
            await refund(db, u, refund_part, "Возврат за варианты, которые не получились", j.id)
        await db.commit()
        return j, u


async def _fail(job_id: int, reason: str):
    async with Session() as db:
        j = await db.get(Job, job_id)
        if j is None:
            return
        j.status, j.error, j.stage = "failed", reason[:500], "Ошибка"
        j.finished_at = now()
        u = await db.get(User, j.user_id)
        if u and j.cost:
            await refund(db, u, j.cost, "Возврат: генерация не удалась", j.id)
        await db.commit()
    log.warning("job %s failed: %s", job_id, reason)


async def _notify(j: Job, u: User, what: str):
    if u and u.can_message and j.kind in ("video", "music"):
        await bot.send(u.tg_id, f"Готово: {what} «{j.prompt[:60]}»", bot.open_app_markup("Открыть", f"#/archive?job={j.id}"))


# ---------------- image ----------------
async def run_image(job: Job):
    p = job.params or {}
    hint = STYLE_HINT.get(p.get("style", "Фото"), "")
    refs = p.get("refs") or []
    route = ai.image_route(p.get("style", "Фото"), bool(refs))
    await _update(job.id, status="running", progress=4, stage="Продумываю детали")
    prompt = await ai.enhance_prompt(job.prompt, hint, bool(refs))
    if prompt == job.prompt and hint:
        prompt = f"{job.prompt}. Style: {hint}. Do not add any text unless asked."
    await _update(job.id, params={**p, "enhanced": prompt[:2000], "model": ai.IMAGE_ROUTES[route]["model"]})
    n = 1
    done = 0

    async def one(i):
        nonlocal done
        data = await ai.image(prompt, p.get("aspect", "1:1"), refs, route)
        rel = save_bytes(job, f"v{i + 1}.png", data)
        th = await asyncio.to_thread(make_thumb, rel)
        done += 1
        await _update(job.id, progress=95, stage="Сохраняю")
        return {"path": rel, "type": "image", "w": 0, "h": 0, **({"thumb": th} if th else {})}

    await _update(job.id, progress=10, stage="Рисую варианты")
    res = await asyncio.gather(*[one(i) for i in range(n)], return_exceptions=True)
    files = [r for r in res if isinstance(r, dict)]
    errs = [r for r in res if not isinstance(r, dict)]
    if not files:
        raise RuntimeError(str(errs[0]) if errs else "нет картинок")
    part = round(job.cost * len(errs) / n) if errs else 0
    return files, part, ""


# ---------------- video ----------------
async def run_video(job: Job):
    p = job.params or {}
    inp = {"prompt": job.prompt, "sound": bool(p.get("sound")), "duration": str(int(p.get("duration", 5))),
           "mode": "pro" if p.get("quality") == "1080p" else "std", "multi_shots": False}
    if p.get("image_url"):
        inp["image_urls"] = [p["image_url"]]
    else:
        inp["aspect_ratio"] = p.get("aspect", "9:16")
    task = p.get("task")  # resume after a worker restart without paying twice
    if not task:
        await _update(job.id, status="running", progress=5, stage="Сценарий")
        task = await kie.create("kling-3.0/video", inp)
        await _update(job.id, params={**p, "task": task}, progress=10, stage="В очереди")
    expect = 90 + 12 * int(p.get("duration", 5)) + (60 if inp["mode"] == "pro" else 0)

    async def tick(state, el):
        pr = 10 if state in ("waiting", "queuing") else min(92, 15 + int(77 * el / expect))
        await _update(job.id, progress=pr, stage=RU_STAGE.get(state, "Рисую кадры"))

    res = await kie.wait(task, tick, timeout=1800)
    urls = res.get("resultUrls") or []
    if not urls:
        raise RuntimeError("видео не вернулось")
    await _update(job.id, progress=95, stage="Сохраняю")
    rel = await download(job, "video.mp4", urls[0])
    files = [{"path": rel, "type": "video"}]
    thumb = rel.rsplit("/", 1)[0] + "/thumb.jpg"
    if await ffmpeg("-i", str(abs_path(rel)), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(abs_path(thumb))):
        th = await asyncio.to_thread(make_thumb, thumb)
        files.append({"path": thumb, "type": "thumb", **({"thumb": th} if th else {})})
    return files, 0, ""


# ---------------- music ----------------
async def run_music(job: Job):
    p = job.params or {}
    style = ", ".join(x for x in [p.get("genre"), p.get("mood")] if x)
    inp = {"prompt": job.prompt[:2900], "custom_mode": False, "instrumental": bool(p.get("instrumental", True)), "model": "V6"}
    if style:
        inp["style"] = style
    task = p.get("task")
    if not task:
        await _update(job.id, status="running", progress=5, stage="Пишу трек")
        task = await kie.create("ai-music-api/generate", inp)
        await _update(job.id, params={**p, "task": task}, progress=10, stage="В очереди")

    async def tick(state, el):
        await _update(job.id, progress=min(92, 12 + int(80 * el / 120)), stage="Записываю" if state == "generating" else "В очереди")

    res = await kie.wait(task, tick, timeout=900)
    tracks = res.get("data") or res.get("sunoData") or []
    if isinstance(res, dict) and not tracks and res.get("resultUrls"):
        tracks = [{"audio_url": u} for u in res["resultUrls"]]
    files = []
    for i, t in enumerate(tracks[:2]):
        url = t.get("audio_url") or t.get("audioUrl") or t.get("stream_audio_url")
        if not url:
            continue
        rel = await download(job, f"track{i + 1}.mp3", url, max_mb=60)
        f = {"path": rel, "type": "audio", "title": t.get("title") or "", "duration": t.get("duration") or 0}
        img = t.get("image_url") or t.get("imageUrl")
        if img:
            try:
                f["cover"] = await download(job, f"cover{i + 1}.jpg", img, max_mb=10)
                th = await asyncio.to_thread(make_thumb, f["cover"], 400)
                if th:
                    f["cover_thumb"] = th
            except Exception:
                pass
        files.append(f)
    if not files:
        raise RuntimeError("треки не вернулись")
    return files, 0, ""


# ---------------- tts ----------------
async def run_tts(job: Job):
    p = job.params or {}
    from .routes.voices import TONES
    await _update(job.id, status="running", progress=15, stage="Озвучиваю")
    wav = await ai.speech(job.prompt, p.get("voice"), TONES.get(p.get("tone"), ai.STYLE))
    rel = save_bytes(job, "voice.wav", wav)
    mp3 = rel[:-4] + ".mp3"
    if await ffmpeg("-i", str(abs_path(rel)), "-b:a", "96k", str(abs_path(mp3))):
        abs_path(rel).unlink(missing_ok=True)
        rel = mp3
    return [{"path": rel, "type": "audio", "duration": round(len(wav) / 48000, 1)}], 0, ""


RUNNERS = {"image": run_image, "video": run_video, "music": run_music, "tts": run_tts}
NAMES = {"image": "картинки", "video": "видео", "music": "трек", "tts": "озвучка"}


async def run_job(ctx, job_id: int):
    async with Session() as db:
        job = await db.get(Job, job_id)
    if job is None or job.status not in ("queued", "running"):
        return
    t0 = time.time()
    try:
        files, part, note = await RUNNERS[job.kind](job)
        j, u = await _finish(job_id, files, part, note)
        log.info("job %s %s done in %.0fs", job_id, job.kind, time.time() - t0)
        await _notify(j, u, NAMES[job.kind])
    except Exception as e:  # any failure refunds the credits
        await _fail(job_id, f"{type(e).__name__}: {e}")
