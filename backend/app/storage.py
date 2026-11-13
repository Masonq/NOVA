import os
import shutil
from pathlib import Path

from .config import get_settings
from .models import Job


def job_dir(job: Job) -> Path:
    return Path(get_settings().storage_dir) / str(job.user_id) / str(job.id)


def public_files(job: Job) -> list[dict]:
    """Files are stored under random names, served by nginx at /files/."""
    s = get_settings()
    out = []
    for f in job.files or []:
        out.append({**f, "url": f"{s.public_url}/files/{f['path']}"})
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
