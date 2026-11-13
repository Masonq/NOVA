import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from .. import ai
from ..config import get_settings
from ..models import User
from ..security import current_user

router = APIRouter(prefix="/api/voices", tags=["voices"])
TONES = {
    "Спокойно": "Говори по-русски спокойно и мягко, ровным темпом, тёплым голосом.",
    "Бодро": "Говори по-русски бодро и энергично, с улыбкой, живым темпом.",
    "Шёпот": "Говори по-русски тихим доверительным шёпотом, медленно.",
    "Диктор": "Читай по-русски как профессиональный диктор: чётко, уверенно, с правильными паузами.",
}
SAMPLE = "Привет! Я NOVA. Расскажу, покажу и озвучу всё, что захочешь."
_locks: dict[str, asyncio.Lock] = {}


@router.get("")
async def voices(u: User = Depends(current_user)):
    return {"default": get_settings().tts_voice, "tones": list(TONES),
            "voices": [{"id": k, "name": v} for k, v in ai.VOICES.items()]}


@router.get("/{vid}/sample")
async def sample(vid: str, u: User = Depends(current_user)):
    """Short sample per voice, generated once and cached; free for the user."""
    if vid not in ai.VOICES:
        raise HTTPException(404, "Нет такого голоса")
    s = get_settings()
    d = Path(s.storage_dir) / "samples"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{vid}.wav"
    lock = _locks.setdefault(vid, asyncio.Lock())
    async with lock:
        if not f.exists():
            try:
                f.write_bytes(await ai.speech(SAMPLE, vid))
            except ai.AIError:
                raise HTTPException(503, "Голос сейчас недоступен, попробуйте позже")
    return {"url": f"{s.public_url}/files/samples/{vid}.wav"}
