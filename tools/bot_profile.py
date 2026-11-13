"""Bot profile: photo, description («Что умеет этот бот?»), short description (profile and shared links), commands.
Applied by the installer only when something here changed (Telegram rate-limits these calls)."""
import hashlib
import json
import sys
from pathlib import Path

import httpx

APP = Path("/opt/nova")
AVATAR = APP / "deploy/brand/bot_avatar.jpg"
MARK = APP / ".bot-profile"

SHORT = "Голосовой ИИ-агент: картинки, видео, песни, озвучка, клипы и поздравления — одной фразой. 100 кредитов в подарок 🎁"

DESCRIPTION = """NOVA — твоя ИИ-студия прямо в Telegram.

🎙 Скажи голосом — агент сам всё сделает
🖼 Картинки и логотипы в высоком качестве
🎬 Видео из текста или из твоего фото
🎵 Песни с вокалом — даже на твой текст
🗣 Озвучка живыми голосами, дуэты
📱 Клипы и ролики под ключ, с субтитрами
🎁 Поздравление: песня с именем и видео-открытка

Готовые работы приходят прямо в этот чат.
100 кредитов в подарок — жми «Старт» 👇"""

COMMANDS = [{"command": "start", "description": "Открыть NOVA"}]


def env(key: str) -> str:
    for line in (APP / ".env").read_text().splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip()
    return ""


def main() -> int:
    assert len(SHORT) <= 120 and len(DESCRIPTION) <= 512, (len(SHORT), len(DESCRIPTION))
    token = env("BOT_TOKEN")
    if not token:
        print("- Профиль бота: нет токена"); return 0
    digest = hashlib.sha256(AVATAR.read_bytes() + SHORT.encode() + DESCRIPTION.encode() + json.dumps(COMMANDS).encode()).hexdigest()[:16]
    if MARK.exists() and MARK.read_text().strip() == digest:
        print("- Профиль бота: без изменений"); return 0
    api = f"https://api.telegram.org/bot{token}"
    out, ok = [], True
    with httpx.Client(timeout=60) as cl:
        for method, data in (("setMyShortDescription", {"short_description": SHORT}),
                             ("setMyDescription", {"description": DESCRIPTION}),
                             ("setMyCommands", {"commands": COMMANDS})):
            r = cl.post(f"{api}/{method}", json=data).json()
            ok &= bool(r.get("ok")); out.append(f"{method} {'ok' if r.get('ok') else r.get('description')}")
        r = cl.post(f"{api}/setMyProfilePhoto",
                    data={"photo": json.dumps({"type": "static", "photo": "attach://avatar"})},
                    files={"avatar": ("avatar.jpg", AVATAR.read_bytes(), "image/jpeg")}).json()
        ok &= bool(r.get("ok")); out.append(f"setMyProfilePhoto {'ok' if r.get('ok') else r.get('description')}")
    if ok:
        MARK.write_text(digest)
    print("- Профиль бота: " + "; ".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
