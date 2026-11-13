from arq import create_pool
from arq.connections import RedisSettings

from .config import get_settings

_pool = None


async def pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(RedisSettings.from_dsn(get_settings().redis_url))
    return _pool


async def enqueue(job_id: int):
    p = await pool()
    await p.enqueue_job("run_job", job_id, _job_id=f"job-{job_id}")
