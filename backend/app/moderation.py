"""Prompt moderation before a generation is charged. Verdicts: ok | review | block.
Fails open (ok) when the moderation model is unavailable, so the service keeps working."""
import json
import logging
import re

from . import ai

log = logging.getLogger("nova.mod")
MODEL = "google/gemini-3.5-flash-lite"
RULES = """Ты модератор генеративного сервиса (картинки, видео, музыка, озвучка). Оцени запрос пользователя.
block — нельзя делать ни при каких условиях: сексуальный контент с несовершеннолетними или любые намёки на него;
интимные/обнажённые изображения реальных людей и дипфейки реальных людей в компрометирующем виде;
инструкции или пропаганда терроризма, массового насилия, изготовления оружия/наркотиков; призывы к ненависти к группам людей;
выдача себя за реального человека с целью обмана (озвучка голосом реального человека для мошенничества).
review — допустимо, но нужен взгляд человека: откровенный взрослый/эротический контент, реальные известные люди,
политика и политики, кровь и жестокость, логотипы и персонажи известных брендов.
ok — всё остальное.
Ответь строго JSON без пояснений: {"verdict": "ok|review|block", "reason": "коротко по-русски, до 80 символов"}"""


async def check(kind: str, prompt: str) -> tuple[str, str]:
    try:
        raw = await ai.complete(MODEL, [{"role": "system", "content": RULES},
                                        {"role": "user", "content": f"Тип: {kind}\nЗапрос: {prompt[:3000]}"}],
                                timeout=20, temperature=0, response_format={"type": "json_object"})
        m = re.search(r"\{.*\}", raw, re.S)
        d = json.loads(m.group(0)) if m else {}
        v = d.get("verdict")
        if v not in ("ok", "review", "block"):
            return "ok", ""
        return v, str(d.get("reason") or "")[:200]
    except Exception as e:  # fail open, keep a trace
        log.warning("moderation unavailable: %s", e)
        return "ok", ""
