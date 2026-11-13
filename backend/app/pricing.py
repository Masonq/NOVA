"""Credits per action (1 credit ~ $0.01 retail, about cost x3). Stage 5 moves this into the admin panel."""
import math

IMAGE_VARIANTS = 4
PRICE = {
    "image": 40,            # 4 variants, Nano Banana 2.1 (~$0.034 each)
    "video_std_s": 24,      # Kling 3.0 std, per second
    "video_pro_s": 36,      # Kling 3.0 pro (1080p), per second
    "video_sound_k": 1.5,   # sound on
    "music": 30,            # Suno V6, 2 tracks + cover
    "tts_1k": 5,            # Gemini TTS, per 1000 characters
    "tts_min": 2,
}


def cost(kind: str, params: dict, prompt: str = "") -> int:
    if kind == "image":
        return PRICE["image"]
    if kind == "video":
        sec = int(params.get("duration", 5))
        per = PRICE["video_pro_s"] if params.get("quality") == "1080p" else PRICE["video_std_s"]
        k = PRICE["video_sound_k"] if params.get("sound") else 1
        return int(math.ceil(sec * per * k / 5) * 5)
    if kind == "music":
        return PRICE["music"]
    if kind == "tts":
        return max(PRICE["tts_min"], int(math.ceil(len(prompt) / 1000 * PRICE["tts_1k"])))
    raise ValueError(kind)
