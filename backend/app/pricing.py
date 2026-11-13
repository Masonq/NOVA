"""Credits per action and credit packs. Defaults live here; the admin panel stores overrides in the
`settings` table, and every API process re-reads them at most every 20 seconds."""
import copy
import math
import time

DEFAULT_PRICE = {
    "image": 12,            # one picture: Seedream 5.5 2K / GPT Image 2.6 (~$0.03–0.035)
    "image_edit": 18,       # edit of the user's own photo: Nano Banana 2.1 2K (~$0.05–0.06)
    "image_hq": 18,         # «Высокое качество» on top: GPT Image 2.6 high (~$0.13)
    "video_std_s": 24,      # Kling 3.0 std, per second
    "video_pro_s": 36,      # Kling 3.0 pro (1080p), per second
    "video_sound_k": 1.5,   # sound on
    "music": 30,            # Suno V6, 2 tracks + cover
    "tts_1k": 5,            # Gemini TTS, per 1000 characters
    "tts_min": 2,
    "agent_min": 5,         # voice agent, per minute of speech
    "agent_search": 3,      # voice agent, each web search
    "chat_msg": 1,          # text chat, per message
    "combo_fee": 10,        # assembling a clip / reel / video card (ffmpeg, directing)
    "welcome": 100,         # credits for a new user (~$0.35 of model cost if all spent)
    "ref_friend": 50,       # extra credits for a user who came by a friend's link
    "ref_bonus": 100,       # credits for the inviter after the friend's first payment
}
DEFAULT_PACKS = [
    {"id": "p500", "credits": 500, "bonus": 0, "stars": 400, "usd": "4.99", "rub": 449},
    {"id": "p1500", "credits": 1500, "bonus": 150, "stars": 1150, "usd": "14.99", "rub": 1290, "hit": True},
    {"id": "p5000", "credits": 5000, "bonus": 1000, "stars": 3700, "usd": "44.99", "rub": 3790},
]
OLD_DEFAULTS = {"welcome": 300, "ref_friend": 100, "image": 40}
PRICE = dict(DEFAULT_PRICE)
PACKS = copy.deepcopy(DEFAULT_PACKS)
_loaded = 0.0


async def refresh(db, force: bool = False):
    """Pulls admin overrides from the DB (cheap, at most every 20 s per process)."""
    global _loaded
    if not force and time.time() - _loaded < 20:
        return
    from .models import Setting
    row = await db.get(Setting, "prices")
    PRICE.clear(); PRICE.update(DEFAULT_PRICE)
    PACKS.clear(); PACKS.extend(copy.deepcopy(DEFAULT_PACKS))
    if row and isinstance(row.value, dict):
        # values equal to the old defaults are ignored so the new defaults apply after an update
        PRICE.update({k: v for k, v in (row.value.get("price") or {}).items() if k in DEFAULT_PRICE and OLD_DEFAULTS.get(k) != v})
        if row.value.get("packs"):
            PACKS.clear(); PACKS.extend(row.value["packs"])
    _loaded = time.time()


CLIP_SCENES = {"camera": 6, "live": 4}      # 6 × 5 s with camera moves, or 4 × 5 s of live video
LIVE_SEC = 5


def combo_parts(kind: str, params: dict, prompt: str = "") -> dict:
    """Prices of the parts of a combined work (also used for partial refunds)."""
    live = params.get("live") is True
    scene = int(PRICE["image"]) + (int(PRICE["video_std_s"]) * LIVE_SEC if live else 0)
    if kind == "clip":
        n = CLIP_SCENES["live" if live else "camera"]
        return {"scenes": n * scene, "scene": scene, "fee": int(PRICE["combo_fee"])}
    if kind == "reel":
        scenes = params.get("scenes") or []
        chars = sum(len(str(x.get("text") or "")) for x in scenes)
        tts = max(int(PRICE["tts_min"]), int(math.ceil(chars / 1000 * PRICE["tts_1k"])))
        return {"scenes": len(scenes) * scene, "scene": scene, "voice": tts,
                "music": int(PRICE["music"]) if params.get("music", True) else 0, "fee": int(PRICE["combo_fee"])}
    if kind == "greeting":
        parts = params.get("parts") or ["song", "card", "video"]
        out = {}
        if "song" in parts:
            out["song"] = int(PRICE["music"])
        if "card" in parts or "video" in parts:
            out["card"] = int(PRICE["image"]) + int(PRICE["image_hq"])
        if "video" in parts:
            out["video"] = int(PRICE["video_std_s"]) * LIVE_SEC + int(PRICE["combo_fee"])
        return out
    return {}


def cost(kind: str, params: dict, prompt: str = "") -> int:
    if kind == "image":
        base = int(PRICE["image_edit"] if params.get("refs") else PRICE["image"])
        return base + (int(PRICE["image_hq"]) if params.get("hq") else 0)
    if kind == "video":
        sec = int(params.get("duration", 5))
        per = PRICE["video_pro_s"] if params.get("quality") == "1080p" else PRICE["video_std_s"]
        k = PRICE["video_sound_k"] if params.get("sound") else 1
        return int(math.ceil(sec * per * k / 5) * 5)
    if kind == "music":
        extra = 0
        if params.get("voice_chars"):   # a track from a voice-over: the text is read again in rhythm first
            extra = max(int(PRICE["tts_min"]), int(math.ceil(int(params["voice_chars"]) / 1000 * PRICE["tts_1k"])))
        return int(PRICE["music"]) + extra
    if kind in ("clip", "reel", "greeting"):
        return sum(v for k, v in combo_parts(kind, params, prompt).items() if k != "scene")
    if kind == "tts":
        import re
        spoken = re.sub(r"(?m)^\s*\[[^\]]{1,82}\]\s*$", "", prompt or "")      # «[Куплет 1: мужской]» is not read aloud
        return max(int(PRICE["tts_min"]), int(math.ceil(len(spoken.strip()) / 1000 * PRICE["tts_1k"])))
    raise ValueError(kind)
