"""Draws NOVA's own illustration set once (OpenRouter images API, GPT Image, transparent background) into storage/art
as WebP, served at /files/art/<name>.webp. Already drawn pictures are kept; delete a file to redraw it.
Usage: python tools/gen_art.py <storage dir>"""
import base64
import io
import os
import sys
from pathlib import Path

import httpx
from PIL import Image

STYLE = ("Premium glossy 3D illustration for a modern dark-theme mobile app, one object only, centred, slight three-quarter view. "
         "Soft rounded stylised shapes, deep navy-indigo and violet materials with warm polished gold accents, a subtle pattern "
         "of tiny white stars on the dark surfaces, soft studio light with a gentle rim light, clean crisp edges, rich but not busy. "
         "No text, no letters, no background, no floor, no shadow plate — transparent background.")
ITEMS = {
    "gift": ("a gift box with a big satin gold ribbon tied in a bow on top, the box is navy with tiny stars", "high"),
    "bag": ("a plump navy velvet money bag tied with a gold cord, a gold star emblem on the front", "medium"),
    "coins": ("a neat stack of four shiny gold coins, each with an embossed star, slightly fanned", "medium"),
    "trophy": ("a gold trophy cup with two handles and a violet gem on the front", "medium"),
    "mic": ("a retro studio microphone with a navy body and a gold mesh grille on a small stand", "medium"),
    "camera": ("a compact cinema video camera, navy body, gold lens ring, small gold details", "medium"),
    "wand": ("a magic wand with a gold star on its tip and a few soft sparkles around it", "medium"),
    "picture": ("a framed picture of mountains under a moon, navy frame with gold corners", "medium"),
}


def env(k):
    if os.environ.get(k):
        return os.environ[k]
    try:
        for line in open("/opt/nova/.env"):
            if line.startswith(k + "="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def main(store: str) -> int:
    key = env("OPENROUTER_KEY")
    if not key:
        print("Иллюстрации: нет ключа OpenRouter")
        return 0
    d = Path(store) / "art"
    d.mkdir(parents=True, exist_ok=True)
    made = kept = fail = 0
    with httpx.Client(timeout=240) as cl:
        for name, (what, quality) in ITEMS.items():
            f = d / f"{name}.webp"
            if f.exists() and f.stat().st_size > 2000:
                kept += 1
                continue
            body = {"model": "openai/gpt-image-2.6-flare", "prompt": f"{what}. {STYLE}", "n": 1, "aspect_ratio": "1:1",
                    "quality": quality, "background": "transparent"}
            try:
                r = cl.post("https://openrouter.ai/api/v1/images", json=body,
                            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
                if r.status_code != 200:
                    print(f"Иллюстрация {name}: {r.status_code} {r.text[:160]}")
                    fail += 1
                    continue
                it = (r.json().get("data") or [{}])[0]
                raw = base64.b64decode(it["b64_json"]) if it.get("b64_json") else cl.get(it["url"]).content
                im = Image.open(io.BytesIO(raw)).convert("RGBA")
                bbox = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()     # trim the empty margin
                if bbox:
                    im = im.crop(bbox)
                side = max(im.size)
                sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
                sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
                sq.thumbnail((512, 512), Image.LANCZOS)
                sq.save(f, "WEBP", quality=90, method=6)
                made += 1
            except Exception as e:
                print(f"Иллюстрация {name}: {type(e).__name__} {str(e)[:160]}")
                fail += 1
    print(f"Иллюстрации NOVA: нарисовано {made}, уже были {kept}, не получилось {fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "storage"))
