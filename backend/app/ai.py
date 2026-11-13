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


async def image(prompt: str, aspect: str = "1:1", ref_urls: list[str] | None = None, model: str = "google/gemini-nano-banana-2.1") -> bytes:
    """One image through OpenRouter (Nano Banana 2.1). Returns image bytes."""
    import base64
    content = [{"type": "text", "text": prompt}]
    for u in (ref_urls or [])[:4]:
        content.append({"type": "image_url", "image_url": {"url": u}})
    body = {"model": model, "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"], "image_config": {"aspect_ratio": aspect}}
    last = ""
    async with httpx.AsyncClient(timeout=180) as cl:
        for attempt in range(3):
            try:
                r = await cl.post(f"{BASE}/chat/completions", headers=_headers(), json=body)
            except httpx.HTTPError as e:
                last = type(e).__name__
                await asyncio.sleep(2 + attempt)
                continue
            if r.status_code == 200:
                msg = (r.json().get("choices") or [{}])[0].get("message") or {}
                for im in msg.get("images") or []:
                    url = (im.get("image_url") or {}).get("url", "")
                    if url.startswith("data:") and "," in url:
                        return base64.b64decode(url.split(",", 1)[1])
                    if url.startswith("http"):
                        rr = await cl.get(url)
                        if rr.status_code == 200:
                            return rr.content
                last = "модель вернула ответ без картинки" + (": " + str(msg.get("content"))[:120] if msg.get("content") else "")
                continue
            last = f"{r.status_code} {r.text[:200]}"
            if r.status_code not in RETRY_STATUS:
                break
            await asyncio.sleep(2 + 2 * attempt)
    raise AIError(f"картинка: {last}")
