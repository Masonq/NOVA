"""Thin REST client for the Gemini API with a model fallback chain.
The official SDK lags behind new models, so we talk to the REST API directly."""
import asyncio
import json
import logging
from typing import AsyncIterator

import httpx

from .config import get_settings

log = logging.getLogger("nova.gemini")
BASE = "https://generativelanguage.googleapis.com/v1beta"
RETRY_STATUS = {429, 500, 502, 503, 504}


class GeminiError(Exception):
    pass


def _headers():
    return {"x-goog-api-key": get_settings().gemini_key, "Content-Type": "application/json"}


def _models(models: str | list[str]) -> list[str]:
    return [m.strip() for m in (models.split(",") if isinstance(models, str) else models) if m.strip()]


async def generate(models, body: dict, timeout: float = 120) -> dict:
    last = "нет ответа"
    async with httpx.AsyncClient(timeout=timeout) as cl:
        for m in _models(models):
            for attempt in range(2):
                try:
                    r = await cl.post(f"{BASE}/models/{m}:generateContent", headers=_headers(), json=body)
                except httpx.HTTPError as e:
                    last = f"{m}: {type(e).__name__}"
                    await asyncio.sleep(1 + attempt)
                    continue
                if r.status_code == 200:
                    return r.json()
                last = f"{m}: {r.status_code} {r.text[:200]}"
                if r.status_code not in RETRY_STATUS:
                    break
                await asyncio.sleep(1 + 2 * attempt)
    raise GeminiError(last)


async def stream_text(models, contents: list, system: str, timeout: float = 120) -> AsyncIterator[str]:
    """Yields text chunks. Falls back to the next model only if the first one failed before any text."""
    body = {"contents": contents, "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {"temperature": 0.8}}
    last = "нет ответа"
    async with httpx.AsyncClient(timeout=timeout) as cl:
        for m in _models(models):
            sent = False
            try:
                async with cl.stream("POST", f"{BASE}/models/{m}:streamGenerateContent?alt=sse", headers=_headers(), json=body) as r:
                    if r.status_code != 200:
                        last = f"{m}: {r.status_code} {(await r.aread())[:200]!r}"
                        continue
                    async for line in r.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            d = json.loads(line[5:])
                        except json.JSONDecodeError:
                            continue
                        for c in d.get("candidates", []):
                            for p in c.get("content", {}).get("parts", []):
                                if p.get("text") and not p.get("thought"):
                                    sent = True
                                    yield p["text"]
                    if sent:
                        return
            except httpx.HTTPError as e:
                last = f"{m}: {type(e).__name__}"
                if sent:
                    raise GeminiError(last)
    raise GeminiError(last)
