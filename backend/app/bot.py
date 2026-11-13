import logging

import httpx

from .config import get_settings

log = logging.getLogger("nova.bot")


async def call(method: str, payload: dict) -> dict:
    s = get_settings()
    if not s.bot_token:
        return {}
    async with httpx.AsyncClient(timeout=20) as cl:
        r = await cl.post(f"https://api.telegram.org/bot{s.bot_token}/{method}", json=payload)
        d = r.json()
        if not d.get("ok"):
            log.warning("bot %s failed: %s", method, d)
        return d


def open_app_markup(text: str = "Открыть NOVA", path: str = "") -> dict:
    s = get_settings()
    return {"inline_keyboard": [[{"text": text, "web_app": {"url": s.public_url + "/" + path.lstrip("/")}}]]}


async def send(chat_id: int, text: str, markup: dict | None = None) -> dict:
    p = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if markup:
        p["reply_markup"] = markup
    return await call("sendMessage", p)


async def call_files(method: str, data: dict, files: dict) -> dict:
    """Multipart call: files are uploaded from our storage, Telegram never has to fetch our URLs."""
    import json as _json
    s = get_settings()
    if not s.bot_token:
        return {}
    form = {k: (_json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)) for k, v in data.items() if v is not None}
    async with httpx.AsyncClient(timeout=120) as cl:
        r = await cl.post(f"https://api.telegram.org/bot{s.bot_token}/{method}", data=form, files=files)
        d = r.json()
        if not d.get("ok"):
            log.warning("bot %s failed: %s", method, d)
        return d
