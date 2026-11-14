"""Downloads the 3D illustrations used by the app (3dicons by Vijay Verma, CC0 1.0 — public domain) into
storage/3d as small WebP files served at /files/3d/<name>.webp. Already downloaded files are skipped."""
import io
import sys
from pathlib import Path

import httpx
from PIL import Image

CDN = "https://3dicons.sgp1.cdn.digitaloceanspaces.com/v1/dynamic/color/{}-dynamic-color.png"
NAMES = ["gift", "money-bag", "3d-coin", "star", "music", "mic", "headphone", "camera", "video-camera", "picture",
         "magic-trick", "rocket", "trophy", "chat", "wallet", "megaphone", "paint-brush", "color-palette",
         "fire", "medal", "sphere", "bulb", "heart", "flash", "target", "lock", "mail", "tick", "clock"]


def main(out: str) -> int:
    d = Path(out) / "3d"
    d.mkdir(parents=True, exist_ok=True)
    ok = fail = 0
    with httpx.Client(timeout=40, follow_redirects=True) as cl:
        for n in NAMES:
            f = d / f"{n}.webp"
            if f.exists() and f.stat().st_size > 1000:
                ok += 1
                continue
            try:
                r = cl.get(CDN.format(n))
                r.raise_for_status()
                im = Image.open(io.BytesIO(r.content)).convert("RGBA")
                im.thumbnail((320, 320), Image.LANCZOS)
                im.save(f, "WEBP", quality=88, method=6)
                ok += 1
            except Exception as e:
                print(f"3D {n}: {type(e).__name__} {e}"[:200])
                fail += 1
    print(f"3D-картинки: {ok} готово, {fail} не скачалось")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "storage"))
