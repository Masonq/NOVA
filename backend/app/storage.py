import os
import shutil
from pathlib import Path

from .config import get_settings
from .models import Job


def job_dir(job: Job) -> Path:
    """New jobs live in a folder with a random part, so their files cannot be found by counting ids."""
    name = f"{job.id}_{job.dir_token}" if job.dir_token else str(job.id)
    return Path(get_settings().storage_dir) / str(job.user_id) / name


def public_files(job: Job) -> list[dict]:
    """Files are stored under random names, served by nginx at /files/."""
    s = get_settings()
    out = []
    for f in job.files or []:
        x = {**f, "url": f"{s.public_url}/files/{f['path']}"}
        if f.get("thumb"):
            x["thumb_url"] = f"{s.public_url}/files/{f['thumb']}"
        if f.get("cover"):
            x["cover_url"] = f"{s.public_url}/files/{f.get('cover_thumb') or f['cover']}"
        out.append(x)
    return out


def remove_job_files(job: Job) -> None:
    d = job_dir(job)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    for f in job.files or []:
        p = Path(get_settings().storage_dir) / f.get("path", "")
        if p.is_file():
            try:
                os.remove(p)
            except OSError:
                pass


import asyncio
import secrets

import httpx


def rel_path(job: Job, name: str) -> str:
    return str(job_dir(job).relative_to(get_settings().storage_dir)) + "/" + name


def save_bytes(job: Job, name: str, data: bytes) -> str:
    d = job_dir(job)
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(data)
    return rel_path(job, name)


async def download(job: Job, name: str, url: str, max_mb: int = 300) -> str:
    d = job_dir(job)
    d.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=300, follow_redirects=True) as cl:
        async with cl.stream("GET", url) as r:
            r.raise_for_status()
            size = 0
            with open(d / name, "wb") as f:
                async for chunk in r.aiter_bytes(1 << 16):
                    size += len(chunk)
                    if size > max_mb << 20:
                        raise ValueError("файл слишком большой")
                    f.write(chunk)
    return rel_path(job, name)


async def ffmpeg(*args: str, timeout: int = 120) -> bool:
    try:
        p = await asyncio.create_subprocess_exec("ffmpeg", "-y", "-loglevel", "error", *args,
                                                 stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err = await asyncio.wait_for(p.communicate(), timeout)
        return p.returncode == 0
    except (FileNotFoundError, asyncio.TimeoutError):
        return False


def abs_path(rel: str) -> Path:
    return Path(get_settings().storage_dir) / rel


def upload_dir(user_id: int) -> Path:
    d = Path(get_settings().storage_dir) / str(user_id) / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def new_upload_name(ext: str) -> str:
    return f"{secrets.token_urlsafe(10)}.{ext}"


def make_thumb(rel: str, size: int = 640) -> str | None:
    """Small WebP preview next to the original (archive, home and carousels load these)."""
    try:
        from PIL import Image
        src = abs_path(rel)
        out = rel.rsplit(".", 1)[0] + ".thumb.webp"
        with Image.open(src) as im:
            if im.mode in ("RGBA", "LA", "P"):        # transparent logos: on white, not on black
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            im = im.convert("RGB")
            im.thumbnail((size, size))
            im.save(abs_path(out), "WEBP", quality=78, method=4)
        return out
    except Exception:
        return None
