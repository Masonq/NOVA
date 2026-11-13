"""Combined works: a clip for a track, a reel from a topic, a greeting (song + card + video card).
Every finished step is saved into the job's params, so a restart of the worker continues where it stopped
and never pays a provider twice. Optional parts that fail are refunded; the essential ones fail the job (full refund)."""
import asyncio
import io
import logging
import re
import wave

from . import ai, kie
from .config import get_settings
from .models import Job
from .pricing import CLIP_SCENES, LIVE_SEC, combo_parts
from .storage import abs_path, download, ffmpeg, make_thumb, save_bytes

log = logging.getLogger("nova.combo")
W, H, FPS = 1080, 1920, 30
FONT_DIR = "/usr/share/fonts/truetype/dejavu"


# ---------------- small helpers ----------------
class Steps:
    """Checkpoints stored in job.params["st"]."""
    def __init__(self, job: Job, update):
        self.job, self.update = job, update
        self.p = dict(job.params or {})
        self.st = dict(self.p.get("st") or {})

    async def save(self, **kw):
        self.st.update(kw)
        self.p["st"] = self.st
        await self.update(self.job.id, params=self.p)


def public(rel: str) -> str:
    return f"{get_settings().public_url}/files/{rel}"


def wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()


def pad_wav(data: bytes, seconds: float) -> bytes:
    with wave.open(io.BytesIO(data)) as r:
        params, frames = r.getparams(), r.readframes(r.getnframes())
    need = int(seconds * params.framerate) * params.sampwidth * params.nchannels
    out = io.BytesIO()
    with wave.open(out, "wb") as o:
        o.setparams(params)
        o.writeframes(frames + b"\x00" * max(0, need - len(frames)))
    return out.getvalue()


async def media_seconds(rel: str) -> float:
    proc = await asyncio.create_subprocess_exec("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                                str(abs_path(rel)), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    out, _ = await proc.communicate()
    try:
        return float(out.decode().strip())
    except ValueError:
        return 0.0


def rel_in(job_rel_dir: str, name: str) -> str:
    return job_rel_dir.rsplit("/", 1)[0] + "/" + name if "/" in job_rel_dir else name


async def must(ok: bool, what: str):
    if not ok:
        raise RuntimeError(f"не удалось собрать: {what}")


# ---------------- pictures and motion ----------------
async def picture(job: Job, name: str, prompt: str, aspect: str = "9:16", route: str = "picture") -> str:
    data = await ai.image(prompt, aspect, [], route)
    rel = save_bytes(job, name, data)
    await asyncio.to_thread(make_thumb, rel)
    return rel


MOVES = [("1.0+0.12*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),            # push in
         ("1.12-0.12*on/{n}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"),           # pull out
         ("1.10", "(iw-iw/zoom)*on/{n}", "ih/2-(ih/zoom/2)"),                   # pan right
         ("1.10", "(iw-iw/zoom)*(1-on/{n})", "ih/2-(ih/zoom/2)")]               # pan left


async def camera(src_rel: str, out_rel: str, seconds: float, idx: int) -> str:
    """A still picture with a slow camera move (Ken Burns), 1080×1920."""
    n = max(1, int(seconds * FPS))
    z, x, y = (m.format(n=n) for m in MOVES[idx % len(MOVES)])
    vf = (f"scale={int(W * 1.5)}:{int(H * 1.5)}:force_original_aspect_ratio=increase,crop={int(W * 1.5)}:{int(H * 1.5)},"
          f"zoompan=z='{z}':x='{x}':y='{y}':d=1:s={W}x{H}:fps={FPS},format=yuv420p")
    await must(await ffmpeg("-framerate", str(FPS), "-loop", "1", "-t", f"{seconds:.2f}", "-i", str(abs_path(src_rel)),
                             "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-an", str(abs_path(out_rel))), "сцена")
    return out_rel


async def fit(src_rel: str, out_rel: str, seconds: float) -> str:
    """A live shot cropped to 1080×1920 and looped or cut to the scene's length."""
    vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p"
    await must(await ffmpeg("-stream_loop", "-1", "-i", str(abs_path(src_rel)), "-t", f"{seconds:.2f}", "-vf", vf,
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-an", str(abs_path(out_rel))), "живая сцена")
    return out_rel


async def live(job: Job, name: str, image_rel: str, prompt: str) -> str:
    """Kling animates a picture (5 s, no sound)."""
    task = await kie.create("kling-3.0/video", {"prompt": prompt[:900], "sound": False, "duration": str(LIVE_SEC), "mode": "std",
                                                "multi_shots": False, "image_urls": [public(image_rel)]})
    res = await kie.wait(task, None, timeout=1500)
    urls = res.get("resultUrls") or []
    if not urls:
        raise RuntimeError("видео не вернулось")
    return await download(job, name, urls[0])


async def concat(parts: list[str], out_rel: str) -> str:
    lst = abs_path(out_rel).with_suffix(".txt")
    lst.write_text("".join(f"file '{abs_path(p)}'\n" for p in parts))
    await must(await ffmpeg("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(abs_path(out_rel))), "склейка")
    lst.unlink(missing_ok=True)
    return out_rel


# ---------------- subtitles ----------------
def _ass_time(t: float) -> str:
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def ass(lines: list[tuple[float, float, str]]) -> str:
    head = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: S,DejaVu Sans,66,&H00FFFFFF,&H00FFFFFF,&H00101010,&H64000000,-1,0,0,0,100,100,0,0,1,5,0,2,80,80,430,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    ev = "".join(f"Dialogue: 0,{_ass_time(a)},{_ass_time(b)},S,,0,0,0,,{re.sub(r'[{}]', '', t).strip()}\n"
                 for a, b, t in lines if t.strip() and b > a)
    return head + ev


def chunks(text: str, start: float, end: float, size: int = 5) -> list[tuple[float, float, str]]:
    """Spreads a scene's voice-over over its time in short lines, by length."""
    words = text.split()
    groups = [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [""]
    total = sum(len(g) for g in groups) or 1
    out, t = [], start
    for g in groups:
        d = (end - start) * len(g) / total
        out.append((t, t + d, g))
        t += d
    return out


def sung_lines(words: list[dict], frm: float, to: float) -> list[tuple[float, float, str]]:
    """Suno's aligned words inside the clip window into lines (section tags dropped), times relative to the window."""
    out, cur, a, last = [], [], None, None
    for w in words:
        s, e = float(w.get("startS") or 0), float(w.get("endS") or 0)
        if e < frm or s > to:
            continue
        raw = str(w.get("word") or "")
        txt = re.sub(r"\[[^\]]*\]", "", raw).strip()
        brk = "\n" in raw.strip() or (last is not None and s - last > 0.7)
        if cur and (brk or len(cur) >= 5):
            out.append((a - frm, last - frm + 0.15, " ".join(cur)))
            cur, a = [], None
        if txt:
            cur.append(txt.replace("\n", " "))
            a = s if a is None else a
            last = e
    if cur:
        out.append((a - frm, min(last, to) - frm + 0.15, " ".join(cur)))
    return out


async def finish_video(job: Job, video_rel: str, audio_rel: str, out_rel: str, seconds: float, subs: list | None) -> list[dict]:
    """Picture + sound (+ burned subtitles) → mp4 with a thumbnail."""
    vf = []
    if subs:
        sub_path = abs_path(out_rel).with_suffix(".ass")
        sub_path.write_text(ass(subs), encoding="utf-8")
        vf = ["-vf", f"ass={sub_path}:fontsdir={FONT_DIR}"]
    await must(await ffmpeg("-i", str(abs_path(video_rel)), "-i", str(abs_path(audio_rel)), *vf, "-map", "0:v", "-map", "1:a",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
                            "-t", f"{seconds:.2f}", "-movflags", "+faststart", str(abs_path(out_rel))), "видео со звуком")
    files = [{"path": out_rel, "type": "video", "duration": round(seconds, 1)}]
    thumb = rel_in(out_rel, "thumb.jpg")
    if await ffmpeg("-ss", "1", "-i", str(abs_path(out_rel)), "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4", str(abs_path(thumb))):
        th = await asyncio.to_thread(make_thumb, thumb)
        files.append({"path": thumb, "type": "thumb", **({"thumb": th} if th else {})})
    return files


async def scenes_video(job: Job, steps: Steps, shots: list[dict], durs: list[float], live_mode: bool, prog) -> tuple[str, int]:
    """Pictures for every shot (in parallel), then camera moves or live shots, then one silent video. Returns (rel, refund)."""
    imgs = list(steps.st.get("imgs") or [None] * len(shots))
    sem = asyncio.Semaphore(3)

    async def one_img(i):
        if imgs[i]:
            return
        async with sem:
            imgs[i] = await picture(job, f"s{i + 1}.png", shots[i]["visual"])
    await prog(12, "Рисую сцены")
    await asyncio.gather(*[one_img(i) for i in range(len(shots))])
    await steps.save(imgs=imgs)
    lives, refund = list(steps.st.get("lives") or [None] * len(shots)), 0
    if live_mode:
        await prog(35, "Оживляю сцены")

        async def one_live(i):
            if lives[i]:
                return
            try:
                lives[i] = await live(job, f"l{i + 1}.mp4", imgs[i], f"{shots[i].get('move', '')}. {shots[i]['visual']}")
            except Exception as e:      # this scene stays a picture with a camera move; its live part is refunded
                log.warning("live scene %s of job %s: %s", i, job.id, e)
                lives[i] = ""
        await asyncio.gather(*[one_live(i) for i in range(len(shots))])
        await steps.save(lives=lives)
        from .pricing import PRICE
        refund = sum(int(PRICE["video_std_s"]) * LIVE_SEC for x in lives if x == "")
    await prog(80, "Монтирую")
    parts = []
    for i, d in enumerate(durs):
        out = rel_in(imgs[i], f"p{i + 1}.mp4")
        parts.append(await (fit(lives[i], out, d) if live_mode and lives[i] else camera(imgs[i], out, d, i)))
    return await concat(parts, rel_in(imgs[0], "scenes.mp4")), refund


# ---------------- music ----------------
async def suno(job: Job, inp: dict, name: str) -> dict:
    task = await kie.create("ai-music-api/generate", inp)
    res = await kie.wait(task, None, timeout=900)
    t = (res.get("data") or res.get("sunoData") or [{}])[0]
    url = t.get("audio_url") or t.get("audioUrl") or t.get("stream_audio_url")
    if not url:
        raise RuntimeError("трек не вернулся")
    rel = await download(job, f"{name}.mp3", url, max_mb=60)
    f = {"path": rel, "type": "audio", "title": t.get("title") or inp.get("title") or "", "duration": t.get("duration") or 0,
         "task": task, "sid": t.get("id") or ""}
    img = t.get("image_url") or t.get("imageUrl")
    if img:
        try:
            f["cover"] = await download(job, f"{name}_cover.jpg", img, max_mb=10)
            th = await asyncio.to_thread(make_thumb, f["cover"], 400)
            if th:
                f["cover_thumb"] = th
        except Exception:
            pass
    return f


async def aligned_words(task: str, sid: str) -> list[dict]:
    """Suno's lyrics with the time of every word. Empty when not available."""
    if not task:
        return []
    try:
        if not sid:
            st = await kie.status(task)
            sid = ((st.get("result") or {}).get("data") or [{}])[0].get("id") or ""
        if not sid:
            return []
        d = await kie.create_sync("ai-music-api/timeStamped-lyrics", {"task_id": task, "audio_id": sid})
        return (((d or {}).get("data") or {}).get("data") or {}).get("alignedWords") or []
    except Exception as e:
        log.warning("timestamped lyrics: %s", e)
        return []


def chorus_start(words: list[dict], fallback: float) -> float:
    for w in words:
        if re.search(r"\[(chorus|припев|hook|хук)", str(w.get("word") or ""), re.I):
            return max(0.0, float(w.get("startS") or 0) - 0.4)
    first = next((float(w.get("startS") or 0) for w in words if re.sub(r"\[[^\]]*\]", "", str(w.get("word") or "")).strip()), None)
    return max(0.0, first - 0.5) if first is not None else fallback


async def cut_audio(src_rel: str, out_rel: str, start: float, seconds: float) -> str:
    af = f"afade=t=in:st=0:d=0.4,afade=t=out:st={max(0.0, seconds - 1.2):.2f}:d=1.2"
    await must(await ffmpeg("-ss", f"{start:.2f}", "-t", f"{seconds:.2f}", "-i", str(abs_path(src_rel)), "-af", af,
                            "-c:a", "aac", "-b:a", "192k", str(abs_path(out_rel))), "фрагмент трека")
    return out_rel


# ---------------- clip for a track ----------------
async def run_clip(job: Job, update) -> tuple[list, int, str]:
    from .db import Session
    steps = Steps(job, update)
    p = steps.p
    async with Session() as db:
        src = await db.get(Job, int(p["track_job"]))
    track = next(x for x in src.files if x.get("type") == "audio")
    live_mode = p.get("live") is True
    n = CLIP_SCENES["live" if live_mode else "camera"]
    total = n * LIVE_SEC

    async def prog(pr, stage):
        await update(job.id, status="running", progress=pr, stage=stage)
    lyrics = ((src.params or {}).get("brief") or {}).get("lyrics") or src.prompt
    style = ((src.params or {}).get("brief") or {}).get("style") or (src.params or {}).get("genre") or ""
    if not steps.st.get("shots"):
        await prog(4, "Придумываю сцены")
        await steps.save(shots=await ai.clip_shots(lyrics, style, n))
    words = await aligned_words(track.get("task") or (src.params or {}).get("task") or "", track.get("sid") or "")
    dur = float(track.get("duration") or 0) or await media_seconds(track["path"])
    start = min(chorus_start(words, max(0.0, dur * 0.25)), max(0.0, dur - total))
    video, refund = await scenes_video(job, steps, steps.st["shots"], [LIVE_SEC] * n, live_mode, prog)
    await prog(90, "Свожу со звуком")
    audio = await cut_audio(track["path"], rel_in(video, "clip_audio.m4a"), start, total)
    subs = sung_lines(words, start, start + total) if p.get("subs", True) and words else None
    files = await finish_video(job, video, audio, rel_in(video, "clip.mp4"), total, subs)
    note = "часть сцен сделана с движением камеры — за них вернулись кредиты" if refund else ""
    return files, refund, note


# ---------------- reel from a topic ----------------
async def run_reel(job: Job, update) -> tuple[list, int, str]:
    steps = Steps(job, update)
    p = steps.p
    scenes = p["scenes"]
    live_mode = p.get("live") is True
    voice = p.get("voice") or "Sulafat"

    async def prog(pr, stage):
        await update(job.id, status="running", progress=pr, stage=stage)
    await prog(4, "Озвучиваю сценарий")
    # voice-over: one recording per scene; the scene lasts as long as its words (+ a breath)
    if not steps.st.get("voice"):
        wavs = [await ai.speech(s["text"], voice, ai.STYLE) for s in scenes]
        durs = [max(2.4, wav_seconds(w) + 0.35) for w in wavs]
        whole = ai.join_wavs([pad_wav(w, d) for w, d in zip(wavs, durs)], gap=0)
        await steps.save(voice=save_bytes(job, "voice.wav", whole), durs=durs)
    durs = steps.st["durs"]
    total = sum(durs)
    music_task = None
    if p.get("music", True) and not steps.st.get("music"):
        music_task = asyncio.create_task(suno(job, {"custom_mode": True, "instrumental": True, "model": "V6",
                                                    "title": (p.get("title") or "NOVA")[:80], "style": p.get("music_style") or "warm cinematic, instrumental"}, "music"))
    shots = [{"visual": s["visual"], "move": "slow push in"} for s in scenes]
    video, refund = await scenes_video(job, steps, shots, durs, live_mode, prog)
    note = "часть сцен сделана с движением камеры — за них вернулись кредиты" if refund else ""
    audio = steps.st["voice"]
    if music_task:
        try:
            await steps.save(music=(await music_task)["path"])
        except Exception as e:          # no music: the reel goes with the voice only, the music is refunded
            log.warning("reel music: %s", e)
            await steps.save(music="")
            refund += combo_parts("reel", p)["music"]
            note = (note + "; " if note else "") + "фоновая музыка не получилась — за неё вернулись кредиты"
    if steps.st.get("music"):
        await prog(88, "Свожу голос и музыку")
        mixed = rel_in(audio, "mix.m4a")
        fc = (f"[1:a]volume=0.17,atrim=0:{total:.2f},afade=t=out:st={max(0.0, total - 1.5):.2f}:d=1.5[m];"
              "[0:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
        await must(await ffmpeg("-i", str(abs_path(audio)), "-stream_loop", "-1", "-i", str(abs_path(steps.st["music"])),
                                "-filter_complex", fc, "-map", "[a]", "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.2f}",
                                str(abs_path(mixed))), "звук")
        audio = mixed
    subs = None
    if p.get("subs", True):
        subs, t = [], 0.0
        for s, d in zip(scenes, durs):
            subs += chunks(s["text"], t + 0.1, t + d - 0.25)
            t += d
    files = await finish_video(job, video, audio, rel_in(video, "reel.mp4"), total, subs)
    return files, refund, note


# ---------------- greeting: song + card + video card ----------------
async def run_greeting(job: Job, update) -> tuple[list, int, str]:
    steps = Steps(job, update)
    p = steps.p
    parts = p.get("parts") or ["song", "card", "video"]

    async def prog(pr, stage):
        await update(job.id, status="running", progress=pr, stage=stage)
    if not steps.st.get("brief"):
        await prog(4, "Пишу песню и открытку")
        await steps.save(brief=await ai.greeting_brief(p.get("name", ""), p.get("occasion", ""), job.prompt, p.get("voices") or "auto"))
    b = steps.st["brief"]
    files, refund, notes = [], 0, []
    song_task = None
    if "song" in parts and not steps.st.get("song"):
        vocals = p.get("voices") if p.get("voices") in ("male", "female") else ""
        inp = {"custom_mode": True, "instrumental": False, "model": "V6", "title": b["title"], "style": b["style"], "lyrics": b["lyrics"]}
        if vocals:
            inp["vocal_gender"] = "m" if vocals == "male" else "f"
        song_task = asyncio.create_task(suno(job, inp, "song"))
    card = steps.st.get("card")
    if ("card" in parts or "video" in parts) and not card:
        await prog(15, "Рисую открытку")
        prompt = f'{b["card_visual"]}. The greeting written on the card, large and beautiful: "{b["card_text"]}".' + ai.exact_text(f'«{b["card_text"]}»')
        card = await picture(job, "card.png", prompt, "3:4" if "video" not in parts else "9:16", "hq")
        await steps.save(card=card)
    if song_task:
        await prog(30, "Записываю песню")
        await steps.save(song=await song_task)
    song = steps.st.get("song")
    if "video" in parts:
        try:
            await prog(55, "Оживляю открытку")
            anim = steps.st.get("anim") or await live(job, "card_live.mp4", card, "gentle festive motion, sparkles, soft light, the text stays sharp and readable")
            await steps.save(anim=anim)
            seconds = 20.0
            if song:
                words = await aligned_words(song.get("task", ""), song.get("sid", ""))
                start = chorus_start(words, 15.0)
                audio = await cut_audio(song["path"], rel_in(card, "card_audio.m4a"), start, seconds)
            else:
                audio = await cut_audio(anim, rel_in(card, "card_audio.m4a"), 0, seconds)
            await prog(85, "Собираю видео-открытку")
            loop = await fit(anim, rel_in(card, "card_loop.mp4"), seconds)
            files += await finish_video(job, loop, audio, rel_in(card, "greeting.mp4"), seconds, None)
        except Exception as e:
            log.warning("greeting video %s: %s", job.id, e)
            refund += combo_parts("greeting", p).get("video", 0)
            notes.append("видео-открытка не получилась — за неё вернулись кредиты")
    if card and "card" in parts:
        files.append({"path": card, "type": "image", "thumb": card.rsplit(".", 1)[0] + ".thumb.webp"})
    if song:
        files.append(song)
    if not files:
        raise RuntimeError("ничего не получилось")
    return files, refund, "; ".join(notes)
