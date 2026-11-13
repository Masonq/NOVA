"""Models via OpenRouter (OpenAI-compatible): chat with streaming, Gemini voices for speech.
One key, pay-as-you-go, no Google billing needed."""
import asyncio
import io
import json
import logging
import wave
from typing import AsyncIterator

import httpx

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
    body = {"messages": [{"role": "system", "content": system}, *messages], "stream": True, "temperature": 0.8}
    last = "нет ответа"
    async with httpx.AsyncClient(timeout=timeout) as cl:
        for m in _models(models):
            sent = False
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
                        for ch in d.get("choices", []):
                            t = (ch.get("delta") or {}).get("content")
                            if t:
                                sent = True
                                yield t
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
                    c = r.json()["choices"][0]["message"].get("content")
                    return c if isinstance(c, str) else "".join(p.get("text", "") for p in (c or []))
                last = f"{m}: {r.status_code} {r.text[:200]}"
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
    async with httpx.AsyncClient(timeout=90) as cl:
        for attempt in range(3):
            try:
                r = await cl.post(f"{BASE}/audio/speech", headers=_headers(), json=body)
            except httpx.HTTPError as e:
                last = type(e).__name__
                await asyncio.sleep(1 + attempt)
                continue
            if r.status_code == 200 and r.content:
                return pcm_to_wav(r.content)
            last = f"{r.status_code} {r.text[:200]}"
            if r.status_code not in RETRY_STATUS:
                break
            await asyncio.sleep(1 + 2 * attempt)
    raise AIError(f"озвучка: {last}")


# The best model per task at a mid price (Nov 2026): Seedream 5.5 for pictures, GPT Image 2.6 for logos and text,
# Nano Banana 2.1 for edits of the user's own photo (keeps faces and objects recognisable).
IMAGE_ROUTES = {
    "picture": {"model": "bytedance-seed/seedream-5-5", "resolution": "2K"},
    "logo": {"model": "openai/gpt-image-2.6-flare", "quality": "medium"},
    "edit": {"model": "google/gemini-nano-banana-2.1", "resolution": "2K"},
}
GPT_ASPECTS = {"1:1", "3:2", "2:3", "4:3", "3:4", "16:9", "9:16", "21:9"}


def image_route(style: str, has_ref: bool) -> str:
    return "edit" if has_ref else "logo" if style == "Логотип" else "picture"


async def image(prompt: str, aspect: str = "1:1", ref_urls: list[str] | None = None, route: str = "picture") -> bytes:
    """One image through the OpenRouter images API, model chosen by the task (see IMAGE_ROUTES)."""
    import base64
    r0 = IMAGE_ROUTES.get(route, IMAGE_ROUTES["picture"])
    body = {"prompt": prompt, "aspect_ratio": aspect if (route != "logo" or aspect in GPT_ASPECTS) else "1:1", "n": 1, **r0}
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
            if r.status_code not in RETRY_STATUS:
                break
            await asyncio.sleep(2 + 2 * attempt)
    raise AIError(f"картинка: {last}")


ENHANCE = """You write prompts for an image generation model. Turn the user's request (usually Russian) into one rich English prompt.
Describe: subject and key details, composition and framing, lighting, colour palette, materials and textures, mood, and the style given.
Rules: keep the user's intent exactly, do not add new subjects; any text that must appear in the image stays EXACTLY as the user wrote it
(same language and letters) in double quotes; for logos: clean vector-style mark, centred, plain background, no mockup;
for photos: realistic camera and lens details; when a reference photo is attached, describe the change to make, keep the person/object recognisable.
Answer with the prompt only, 60–120 words, no preamble."""


MUSIC_BRIEF = """You prepare a request for the Suno music model. Suno rejects real artist and band names, so never output them.
From the user's request (usually Russian) and the chosen genre/mood return strict JSON:
{"style": "comma-separated English style tags, 6–12 tags: genre, sub-genre, tempo/BPM, instruments, vocal type and gender, mood, production",
 "title": "short track title in the user's language, max 40 chars",
 "idea": "what the song is about, in the user's language, max 300 chars, no artist names"}
When the user names an artist, describe that artist's typical sound in the tags instead of the name."""


async def music_brief(prompt: str, genre: str = "", mood: str = "", vocal: bool = False) -> dict:
    """Turns «a track like <artist>» into Suno-safe style tags, a title and an idea. Falls back to simple values."""
    fallback = {"style": ", ".join(x for x in (genre, mood) if x), "title": "", "idea": prompt[:300]}
    try:
        raw = await complete("google/gemini-3.8-flash", [{"role": "system", "content": MUSIC_BRIEF}, {"role": "user", "content":
                             f"Request: {prompt}\nGenre: {genre or 'any'}\nMood: {mood or 'any'}\nVocals: {'yes' if vocal else 'no, instrumental'}"}],
                             timeout=20, temperature=0.5, max_tokens=400, response_format={"type": "json_object"})
        import re as _re
        m = _re.search(r"\{.*\}", raw or "", _re.S)
        d = json.loads(m.group(0)) if m else {}
        out = {"style": str(d.get("style") or "")[:900], "title": str(d.get("title") or "")[:80], "idea": str(d.get("idea") or "")[:2900]}
        return {k: (v or fallback[k]) for k, v in out.items()}
    except Exception:
        return fallback


async def enhance_prompt(prompt: str, style: str = "", has_ref: bool = False) -> str:
    """Rewrites a short request into a detailed prompt. Falls back to the original text on any problem."""
    try:
        user = f"Style: {style or 'any'}\nReference photo attached: {'yes' if has_ref else 'no'}\nRequest: {prompt}"
        out = await complete("google/gemini-3.8-flash", [{"role": "system", "content": ENHANCE}, {"role": "user", "content": user}],
                             timeout=20, temperature=0.6, max_tokens=400)
        out = (out or "").strip().strip('"')
        return out if 30 <= len(out) <= 2000 else prompt
    except Exception:
        return prompt


async def stream_events(model: str, messages: list[dict], tools: list | None = None, timeout: float = 90):
    """Streams ('text', str), then ('tools', [{id,name,arguments}]) if the model called tools."""
    body = {"model": model, "messages": messages, "stream": True, "temperature": 0.7}
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
    c = r.json()["choices"][0]["message"].get("content") or ""
    return c[:1800]
