"""Models via OpenRouter (OpenAI-compatible): chat with streaming, Gemini voices for speech.
One key, pay-as-you-go, no Google billing needed."""
import asyncio
import io
import json
import re
import logging
import wave
from typing import AsyncIterator

import httpx

from . import costs

from .config import get_settings

log = logging.getLogger("nova.ai")
BASE = "https://openrouter.ai/api/v1"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}

VOICES = {  # Gemini voices; Russian works with all of them
    "Sulafat": "тёплый женский", "Aoede": "лёгкий женский", "Leda": "молодой женский", "Kore": "уверенный женский",
    "Puck": "бодрый мужской", "Charon": "спокойный мужской", "Orus": "уверенный мужской", "Fenrir": "энергичный мужской",
}
STYLE = "Говори по-русски живо и тепло, естественным темпом, с лёгкими паузами и улыбкой в голосе, без дикторской интонации."


class AIError(Exception):
    pass


def _headers() -> dict:
    s = get_settings()
    return {"Authorization": f"Bearer {s.openrouter_key}", "Content-Type": "application/json",
            "HTTP-Referer": s.public_url, "X-Title": "NOVA"}


def _models(models) -> list[str]:
    return [m.strip() for m in (models.split(",") if isinstance(models, str) else models) if m.strip()]


async def stream_text(models, messages: list[dict], system: str, timeout: float = 120) -> AsyncIterator[str]:
    """Yields text chunks. Falls back to the next model only if nothing was sent yet."""
    body = {"messages": [{"role": "system", "content": system}, *messages], "stream": True, "temperature": 0.8,
            "stream_options": {"include_usage": True}}
    last = "нет ответа"
    async with httpx.AsyncClient(timeout=timeout) as cl:
        for m in _models(models):
            sent, gid = False, None
            try:
                async with cl.stream("POST", f"{BASE}/chat/completions", headers=_headers(), json={**body, "model": m}) as r:
                    if r.status_code != 200:
                        last = f"{m}: {r.status_code} {(await r.aread())[:200]!r}"
                        continue
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            d = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if d.get("error"):
                            raise AIError(str(d["error"])[:200])
                        gid = d.get("id") or gid
                        if d.get("usage"):
                            costs.openrouter(d, m); gid = None
                        for ch in d.get("choices", []):
                            t = (ch.get("delta") or {}).get("content")
                            if t:
                                sent = True
                                yield t
                    if gid:
                        costs.openrouter(gen_id=gid, note=m)
                    if sent:
                        return
            except (httpx.HTTPError, AIError) as e:
                last = f"{m}: {type(e).__name__} {e}"
                if sent:
                    raise AIError(last)
    raise AIError(last)


async def complete(models, messages: list[dict], timeout: float = 120, **extra) -> str:
    last = "нет ответа"
    async with httpx.AsyncClient(timeout=timeout) as cl:
        for m in _models(models):
            for attempt in range(2):
                try:
                    r = await cl.post(f"{BASE}/chat/completions", headers=_headers(), json={"model": m, "messages": messages, **extra})
                except httpx.HTTPError as e:
                    last = f"{m}: {type(e).__name__}"
                    await asyncio.sleep(1 + attempt)
                    continue
                if r.status_code == 200:
                    costs.openrouter(r.json(), m)
                    c = r.json()["choices"][0]["message"].get("content")
                    return c if isinstance(c, str) else "".join(p.get("text", "") for p in (c or []))
                last = f"{m}: {r.status_code} {r.text[:200]}"
                if r.status_code == 402:
                    costs.out_of_funds("openrouter", r.text[:120])
                if r.status_code not in RETRY_STATUS:
                    break
                await asyncio.sleep(1 + 2 * attempt)
    raise AIError(last)


def pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)
    return buf.getvalue()


async def speech(text: str, voice: str | None = None, instructions: str = STYLE, model: str | None = None) -> bytes:
    """Gemini TTS through OpenRouter. Returns WAV bytes (24 kHz mono)."""
    s = get_settings()
    body = {"model": model or s.tts_model, "input": text, "voice": voice if voice in VOICES else s.tts_voice,
            "instructions": instructions, "response_format": "pcm"}
    last = ""
    import random
    async with httpx.AsyncClient(timeout=90) as cl:
        for attempt in range(5):                     # backoff with jitter: parallel retries don't hit the limit together
            if attempt:
                await asyncio.sleep(min(8.0, 0.7 * 2 ** (attempt - 1)) + random.random() * 0.6)
            try:
                r = await cl.post(f"{BASE}/audio/speech", headers=_headers(), json=body)
            except httpx.HTTPError as e:
                last = type(e).__name__
                continue
            if r.status_code == 200 and not r.content:
                last = "пустой ответ"
                continue
            if r.status_code == 200 and r.content:
                gid = r.headers.get("x-generation-id") or r.headers.get("x-openrouter-generation-id")
                if gid:
                    costs.openrouter(gen_id=gid, note=body["model"])
                else:   # no id in the reply: Gemini TTS bills ~$9 per 1M audio tokens (25 tokens per second of audio)
                    costs.record("openrouter", len(r.content) / 48000 * 25 * 9e-6, body["model"] + " (по длине звука)")
                return pcm_to_wav(r.content)
            last = f"{r.status_code} {r.text[:200]}"
            if r.status_code == 402:
                costs.out_of_funds("openrouter", r.text[:120])
            if r.status_code not in RETRY_STATUS:
                break
    raise AIError(f"озвучка: {last}")


# The best model per task at a mid price (Nov 2026): Seedream 5.5 for pictures, GPT Image 2.6 for logos and text,
# Nano Banana 2.1 for edits of the user's own photo (keeps faces and objects recognisable).
IMAGE_ROUTES = {
    "picture": {"model": "bytedance-seed/seedream-5-5", "resolution": "2K"},
    "logo": {"model": "openai/gpt-image-2.6-flare", "quality": "medium", "background": "opaque"},
    "edit": {"model": "google/gemini-nano-banana-2.1", "resolution": "2K"},
    "hq": {"model": "openai/gpt-image-2.6-flare", "quality": "high", "background": "opaque"},   # «Высокое качество», like ChatGPT
}
GPT_ASPECTS = {"1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9"}


def image_route(style: str, has_ref: bool, hq: bool = False) -> str:
    return "hq" if hq else "edit" if has_ref else "logo" if style == "Логотип" else "picture"


async def image(prompt: str, aspect: str = "1:1", ref_urls: list[str] | None = None, route: str = "picture") -> bytes:
    """One image through the OpenRouter images API, model chosen by the task (see IMAGE_ROUTES)."""
    import base64
    r0 = IMAGE_ROUTES.get(route, IMAGE_ROUTES["picture"])
    body = {"prompt": prompt, "aspect_ratio": aspect if (route not in ("logo", "hq") or aspect in GPT_ASPECTS) else "1:1", "n": 1, **r0}
    if ref_urls:
        body["input_references"] = [{"type": "image_url", "image_url": {"url": u}} for u in ref_urls[:4]]
    last = ""
    async with httpx.AsyncClient(timeout=240) as cl:
        for attempt in range(3):
            try:
                r = await cl.post(f"{BASE}/images", headers=_headers(), json=body)
            except httpx.HTTPError as e:
                last = type(e).__name__
                await asyncio.sleep(2 + attempt)
                continue
            if r.status_code == 200:
                costs.openrouter(r.json(), body["model"])
                for it in r.json().get("data") or []:
                    if it.get("b64_json"):
                        return base64.b64decode(it["b64_json"])
                    if (it.get("url") or "").startswith("http"):
                        rr = await cl.get(it["url"])
                        if rr.status_code == 200:
                            return rr.content
                last = "модель не вернула картинку (возможно, запрос отклонён её фильтрами)"
                break
            last = f"{r.status_code} {r.text[:200]}"
            if r.status_code == 402:
                costs.out_of_funds("openrouter", r.text[:120])
            if r.status_code not in RETRY_STATUS:
                break
            await asyncio.sleep(2 + 2 * attempt)
    raise AIError(f"картинка: {last}")


ENHANCE = """You write prompts for an image generation model. Turn the user's request (usually Russian) into one rich English prompt.
Describe: subject and key details, composition and framing, lighting, colour palette, materials and textures, mood, and the style given.
Rules: keep the user's intent exactly, do not add new subjects; any text that must appear in the image stays EXACTLY as the user wrote it:
same language and alphabet (Cyrillic stays Cyrillic, never translate or transliterate), same words, same punctuation, in double quotes;
never add words of your own to the image (no "TV", "news", slogans, taglines) unless the user asked for them;
for logos: clean flat vector-style mark with crisp shapes, strong contrast, centred on a plain white background, no mockup, no 3D render;
for photos: realistic camera and lens details; when a reference photo is attached, describe the change to make, keep the person/object recognisable.
Answer with the prompt only, 60–120 words, no preamble."""


MUSIC_BRIEF = """You are a music producer preparing a request for the Suno model (custom mode).
Suno rejects real artist and band names: never output them; describe the artist's typical sound instead.
Follow the user's description first. Genre and mood, when given, refine it; when they are empty, infer them from the description.
Several genres or moods may be given (e.g. "Поп, Рэп" and "Энергично, Эпично"): blend ALL of them into one coherent sound
(e.g. pop-rap with a big cinematic chorus), name the blend in the tags, never drop one of them.
Vocals: the user may fix them (male / female / duet) or leave "auto". On auto, decide from the meaning: a dialogue or a love story
between two people → duet; a woman's story or point of view → female; otherwise what fits the genre best.
Mark who sings in every section tag of the lyrics: [Verse 1: Male Vocal], [Chorus: Female Vocal], [Bridge: Duet], [Outro: Male & Female].
For a single singer still use the same tags (all male or all female). Add the vocal type to the style tags
("male vocals", "female vocals" or "male and female duet vocals").
Return strict JSON:
{"vocals": "male | female | duet",
 "title": "track title in the user's language, max 40 chars",
 "style": "comma-separated English tags, 8–14: genre and sub-genre, tempo/BPM, key instruments, vocal type and gender, mood, production style",
 "lyrics": "the full song text in the user's language (Russian by default) with section tags on separate lines:
[Verse 1] [Pre-Chorus] [Chorus] [Verse 2] [Chorus] [Bridge] [Chorus] [Outro]; 2–3 minutes of singing, vivid concrete images,
natural rhymes, a catchy repeatable chorus, about the user's topic; empty string when the track is instrumental"}
For rap / hip-hop / trap: write real rap — verses of 12–16 bars with internal rhymes, multisyllabic rhymes and a steady flow,
a short catchy hook (2–4 lines, repeated), ad-libs in parentheses; tags must say "rap vocals" and the flow
(e.g. melodic rap, autotuned sung-rap, aggressive rap). When an artist reference is given below, match that sound closely."""

ARTIST_HINT = re.compile(r"(в стиле|как у|наподобие|на подобии|по типу|типа|похож|в духе|like|style of|as)\s+\S+", re.I)


async def artist_sound(prompt: str) -> str:
    """When the request references an artist, look up how that artist sounds (web search), without inventing."""
    if not ARTIST_HINT.search(prompt):
        return ""
    body = {"model": "google/gemini-3.8-flash", "plugins": [{"id": "web", "max_results": 4}], "temperature": 0.2, "max_tokens": 350,
            "messages": [{"role": "user", "content": "The request below mentions a musician. Find how this musician sounds and describe it for a "
                          "music producer in English, 5–8 short lines: genres, typical BPM range, beat and instruments, vocal delivery "
                          "(rap/singing, autotune, timbre), mood, typical lyric themes. No song titles. If you can't find the artist, say UNKNOWN.\n\n"
                          f"Request: {prompt}"}]}
    try:
        async with httpx.AsyncClient(timeout=40) as cl:
            r = await cl.post(f"{BASE}/chat/completions", headers=_headers(), json=body)
        if r.status_code != 200:
            return ""
        costs.openrouter(r.json(), "web search")
        txt = (r.json()["choices"][0]["message"].get("content") or "").strip()
        return "" if "UNKNOWN" in txt[:40] else txt[:1200]
    except Exception:
        return ""


async def music_brief(prompt: str, genre: str = "", mood: str = "", vocal: bool = False, voices: str = "auto") -> dict:
    """Writes the lyrics, the style tags and the title for Suno custom mode. Falls back to simple values."""
    fallback = {"title": prompt[:40], "style": ", ".join(x for x in (genre, mood) if x) or "modern pop, catchy, polished production", "lyrics": "",
                "vocals": voices if voices in ("male", "female", "duet") else ""}
    sound = await artist_sound(prompt)
    try:
        raw = await complete("google/gemini-3.8-flash", [{"role": "system", "content": MUSIC_BRIEF}, {"role": "user", "content":
                             f"Description: {prompt}\nGenre: {genre or 'auto'}\nMood: {mood or 'auto'}\nVocals: {('yes, ' + voices) if vocal else 'no, instrumental'}"
                             + (f"\nArtist reference (how the mentioned artist sounds, from the web):\n{sound}" if sound else "")}],
                             timeout=40, temperature=0.8, max_tokens=2500, response_format={"type": "json_object"})
        import re as _re
        m = _re.search(r"\{.*\}", raw or "", _re.S)
        d = json.loads(m.group(0)) if m else {}
        vocals = d.get("vocals") if d.get("vocals") in ("male", "female", "duet") else ""
        if voices in ("male", "female", "duet"):
            vocals = voices                      # the user's choice wins over the model's
        out = {"vocals": vocals if vocal else "", "title": str(d.get("title") or "")[:80], "style": str(d.get("style") or "")[:950],
               "lyrics": str(d.get("lyrics") or "")[:4900] if vocal else ""}
        res = {k: (out[k] or fallback.get(k, "")) for k in out}
        res["reference"] = sound[:600]
        return res
    except Exception:
        return fallback


SECTION = re.compile(r"^\s*\[([^\]:]{1,40})(?::\s*([^\]]{1,40}))?\]\s*$")


def who_of(spec: str) -> str:
    """«мужской», «Женский», «дуэт», «вместе», a voice name — to male / female / duet / a voice id ("" if not said)."""
    t = (spec or "").strip().lower()
    for name in VOICES:
        if name.lower() in t:
            return name
    if any(w in t for w in ("дуэт", "вместе", "оба", "duet", "both")):
        return "duet"
    if "жен" in t or "female" in t or "она" == t:
        return "female"
    if "муж" in t or "male" in t or "он" == t:
        return "male"
    return ""


def parse_sections(text: str) -> list[dict]:
    """Lyrics marked like «[Куплет 1: мужской]» into parts. Empty when the text has no such marks."""
    parts, cur = [], {"label": "", "who": "", "lines": []}
    found = False
    for line in (text or "").splitlines():
        m = SECTION.match(line)
        if m:
            found = True
            if any(l.strip() for l in cur["lines"]):
                parts.append(cur)
            cur = {"label": m.group(1).strip(), "who": who_of(m.group(2) or m.group(1)), "lines": []}
        else:
            cur["lines"].append(line)
    if any(l.strip() for l in cur["lines"]):
        parts.append(cur)
    if not found:
        return []
    return [{"label": p["label"], "who": p["who"], "text": "\n".join(l for l in p["lines"]).strip()} for p in parts]


def suno_lyrics(sections: list[dict]) -> str:
    """Sections back to lyrics with Suno's vocal marks: [Куплет 1: Male Vocal]."""
    tag = {"male": "Male Vocal", "female": "Female Vocal", "duet": "Male & Female Vocals"}
    out = []
    for p in sections:
        who = p["who"] if p["who"] in tag else ("female" if voice_gender(p["who"]) == "female" else "male") if p["who"] in VOICES else ""
        head = p["label"] or "Verse"
        out.append(f"[{head}: {tag[who]}]" if who else f"[{head}]")
        out.append(p["text"])
        out.append("")
    return "\n".join(out).strip()


def voice_gender(voice: str) -> str:
    return "female" if "женский" in VOICES.get(voice, "") else "male"


DUET_SPLIT = """Split song lyrics between a male and a female singer, like a real duet.
Keep the text exactly as given, in order, without changes; only decide who sings each part.
Prefer whole lines and sections: e.g. verses alternate, the chorus is sung together or by the other voice,
dialogue lines go to the speaker they belong to. Return strict JSON: {"parts": [{"who": "male|female", "text": "..."}]}"""


async def read_sections(sections: list[dict], male: str, female: str, default: str, how: str) -> bytes:
    """Each part by its voice, a duet part line by line in turns, glued with pauses into one recording."""
    wavs = []
    for p in sections:
        who = p["who"] or ""
        if who == "duet":
            lines = [l for l in p["text"].splitlines() if l.strip()] or [p["text"]]
            for i, l in enumerate(lines):
                wavs.append(await speech(l, male if i % 2 == 0 else female, how))
        else:
            voice = who if who in VOICES else male if who == "male" else female if who == "female" else default
            wavs.append(await speech(p["text"], voice, how))
    return join_wavs(wavs, gap=0.45)


async def duet_split(text: str) -> list[dict]:
    """Who sings which part. Falls back to alternating halves of the lines."""
    try:
        raw = await complete("google/gemini-3.8-flash", [{"role": "system", "content": DUET_SPLIT}, {"role": "user", "content": text[:4900]}],
                             timeout=30, temperature=0.3, max_tokens=2500, response_format={"type": "json_object"})
        m = re.search(r"\{.*\}", raw or "", re.S)
        parts = [{"who": "female" if p.get("who") == "female" else "male", "text": str(p.get("text") or "").strip()}
                 for p in (json.loads(m.group(0)).get("parts") if m else []) if str(p.get("text") or "").strip()]
        joined = " ".join(p["text"] for p in parts)
        if len(parts) >= 2 and len(joined) >= len(text.strip()) * 0.8:        # nothing important lost
            return parts
    except Exception:
        pass
    lines = [l for l in text.splitlines() if l.strip()] or [text]
    if len(lines) == 1:
        words = text.split(); half = max(1, len(words) // 2)
        lines = [" ".join(words[:half]), " ".join(words[half:])]
    step = max(1, len(lines) // 4)
    return [{"who": "male" if (i // step) % 2 == 0 else "female", "text": l} for i, l in enumerate(lines)]


def join_wavs(wavs: list[bytes], gap: float = 0.25) -> bytes:
    """Glues WAV parts (same format) with a short pause between them."""
    out, params = io.BytesIO(), None
    frames = []
    for w in wavs:
        with wave.open(io.BytesIO(w)) as r:
            params = params or r.getparams()
            frames.append(r.readframes(r.getnframes()))
    silence = b"\x00" * int(params.framerate * gap) * params.sampwidth * params.nchannels
    with wave.open(out, "wb") as o:
        o.setparams(params)
        o.writeframes(silence.join(frames))
    return out.getvalue()


QUOTED = re.compile(r"[«\"“„]([^«»\"“”„]{2,120})[»\"”“]")


def exact_text(prompt: str) -> str:
    """Text the user wants written on the image (in quotes) — added verbatim so the model can't translate or change it."""
    parts = [m.strip() for m in QUOTED.findall(prompt or "") if m.strip()]
    if not parts:
        return ""
    return " The only text on the image, spelled exactly like this, same alphabet: " + "; ".join(f'"{t}"' for t in parts) + ". No other words."


async def enhance_prompt(prompt: str, style: str = "", has_ref: bool = False) -> str:
    """Rewrites a short request into a detailed prompt. Falls back to the original text on any problem."""
    try:
        user = f"Style: {style or 'any'}\nReference photo attached: {'yes' if has_ref else 'no'}\nRequest: {prompt}"
        out = await complete("google/gemini-3.8-flash", [{"role": "system", "content": ENHANCE}, {"role": "user", "content": user}],
                             timeout=20, temperature=0.6, max_tokens=400)
        out = (out or "").strip().strip('"')
        base = out if 30 <= len(out) <= 2000 else (f"{prompt}. Style: {style}." if style else prompt)
        return base + exact_text(prompt)
    except Exception:
        return (f"{prompt}. Style: {style}." if style else prompt) + exact_text(prompt)


async def stream_events(model: str, messages: list[dict], tools: list | None = None, timeout: float = 90):
    """Streams ('text', str), then ('tools', [{id,name,arguments}]) if the model called tools."""
    body = {"model": model, "messages": messages, "stream": True, "temperature": 0.7, "stream_options": {"include_usage": True}}
    gid = None
    if tools:
        body["tools"] = tools
    calls: dict[int, dict] = {}
    async with httpx.AsyncClient(timeout=timeout) as cl:
        async with cl.stream("POST", f"{BASE}/chat/completions", headers=_headers(), json=body) as r:
            if r.status_code != 200:
                raise AIError(f"{r.status_code} {(await r.aread())[:200]!r}")
            async for line in r.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    d = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if d.get("error"):
                    raise AIError(str(d["error"])[:200])
                gid = d.get("id") or gid
                if d.get("usage"):
                    costs.openrouter(d, model); gid = None
                for ch in d.get("choices", []):
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        yield ("text", delta["content"])
                    for tc in delta.get("tool_calls") or []:
                        c = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "arguments": ""})
                        c["id"] = tc.get("id") or c["id"]
                        fn = tc.get("function") or {}
                        c["name"] = fn.get("name") or c["name"]
                        c["arguments"] += fn.get("arguments") or ""
    if gid:
        costs.openrouter(gen_id=gid, note=model)
    if calls:
        yield ("tools", [calls[k] for k in sorted(calls)])


async def web_answer(query: str) -> str:
    """Short answer with web search (OpenRouter web plugin)."""
    body = {"model": "google/gemini-3.8-flash", "plugins": [{"id": "web", "max_results": 4}],
            "messages": [{"role": "user", "content": f"Найди в интернете и ответь по-русски коротко (до 5 предложений), с цифрами и датами: {query}"}]}
    async with httpx.AsyncClient(timeout=60) as cl:
        r = await cl.post(f"{BASE}/chat/completions", headers=_headers(), json=body)
    if r.status_code != 200:
        raise AIError(f"поиск: {r.status_code}")
    costs.openrouter(r.json(), "web search")
    c = r.json()["choices"][0]["message"].get("content") or ""
    return c[:1800]



# ---------------- directing: clips, reels, greetings ----------------
async def _json(system: str, user: str, max_tokens: int = 2500, temperature: float = 0.7) -> dict:
    raw = await complete("google/gemini-3.8-flash", [{"role": "system", "content": system}, {"role": "user", "content": user}],
                         timeout=60, temperature=temperature, max_tokens=max_tokens, response_format={"type": "json_object"})
    m = re.search(r"\{.*\}", raw or "", re.S)
    return json.loads(m.group(0)) if m else {}


CLIP_SCENES = """You are a music video director. From the song's lyrics and sound, plan {n} vertical (9:16) shots for a short clip.
One visual world for all shots: the same main character (describe their look identically in every shot), the same palette and lighting.
Each shot: a vivid, concrete English image prompt, 40–70 words, photographic or cinematic, no text on screen, no real people or brands,
and a short camera move for animation ("slow push in", "orbit left", "handheld walk"). Keep it tasteful.
Return strict JSON: {{"style": "the shared look in 15 words", "shots": [{{"visual": "...", "move": "..."}}]}}"""


async def clip_shots(lyrics: str, style_tags: str, n: int) -> list[dict]:
    d = await _json(CLIP_SCENES.format(n=n), f"Sound: {style_tags}\nLyrics:\n{lyrics[:3500]}")
    shots = [s for s in d.get("shots") or [] if isinstance(s, dict) and s.get("visual")][:n]
    while len(shots) < n:
        shots.append({"visual": f"cinematic vertical shot matching the mood of the song: {style_tags}", "move": "slow push in"})
    look = str(d.get("style") or "")[:200]
    return [{"visual": (look + ". " if look else "") + str(s["visual"])[:900], "move": str(s.get("move") or "slow push in")[:80]} for s in shots]


REEL_SCRIPT = """You write scripts for vertical short videos (Reels, TikTok, Shorts) in Russian.
Topic from the user; target length about {sec} seconds of voice-over (~2.3 words per second in total).
Make {n} scenes. Scene 1 is a strong hook. Each scene: the voice-over text in Russian (one or two short sentences, spoken style, no emojis),
and an English image prompt for that scene, vertical 9:16, vivid and concrete, no text on screen, no real people or brands.
Also a background music style in English tags (no vocals) and a short Russian title.
Return strict JSON: {{"title": "...", "music": "lo-fi, warm, 90 bpm, instrumental", "scenes": [{{"text": "...", "visual": "..."}}]}}"""


async def reel_script(topic: str, seconds: int) -> dict:
    n = 6 if seconds <= 35 else 9
    d = await _json(REEL_SCRIPT.format(sec=seconds, n=n), f"Тема: {topic[:500]}", temperature=0.8)
    scenes = [{"text": str(s.get("text") or "").strip()[:300], "visual": str(s.get("visual") or "").strip()[:900]}
              for s in d.get("scenes") or [] if isinstance(s, dict) and s.get("text")][:10]
    if len(scenes) < 2:
        raise AIError("сценарий не получился, попробуйте сформулировать тему иначе")
    return {"title": str(d.get("title") or topic)[:80], "music": str(d.get("music") or "warm cinematic, instrumental")[:200], "scenes": scenes}


GREETING = """You write a personal congratulation song in Russian and a greeting card.
Use the person's name naturally, at least twice in the chorus. Warm, sincere, a bit of humour if it suits the occasion; no clichés like «желаю счастья, здоровья».
Use details the user gave. Lyrics with section tags on their own lines: [Куплет 1], [Припев], [Куплет 2], [Припев], [Финал]; 1.5–2 minutes.
Card: the exact short greeting line in Russian that will be written on the card (max 40 chars, with the name),
and an English image prompt for a beautiful festive card that leaves clean space for that line.
Return strict JSON: {"title": "...", "style": "English music tags, 8–12", "lyrics": "...", "card_text": "...", "card_visual": "..."}"""


async def greeting_brief(name: str, occasion: str, about: str, voices: str) -> dict:
    d = await _json(GREETING, f"Имя: {name}\nПовод: {occasion}\nО человеке и пожелания: {about or '—'}\nКто поёт: {voices}")
    card = str(d.get("card_text") or f"{occasion}, {name}!")[:60]
    return {"title": str(d.get("title") or f"Для {name}")[:80], "style": str(d.get("style") or "warm pop, celebratory, catchy")[:900],
            "lyrics": str(d.get("lyrics") or "")[:4900], "card_text": card,
            "card_visual": str(d.get("card_visual") or f"festive greeting card for {occasion}, elegant, warm light")[:900]}
