"""Kie.ai task API (video: Kling 3.0, music: Suno V6). Create a task, then poll recordInfo."""
import asyncio
import json
import logging

import httpx

from .config import get_settings

log = logging.getLogger("nova.kie")
BASE = "https://api.kie.ai/api/v1"


class KieError(Exception):
    pass


def _client(timeout: float) -> httpx.AsyncClient:
    """The Kie key is locked to the server's IPv4 address: never let a request leave over IPv6."""
    return httpx.AsyncClient(timeout=timeout, transport=httpx.AsyncHTTPTransport(local_address="0.0.0.0", retries=1))


def _h():
    return {"Authorization": f"Bearer {get_settings().kie_key}", "Content-Type": "application/json"}


async def create(model: str, inp: dict) -> str:
    async with _client(60) as cl:
        for attempt in range(3):
            try:
                r = await cl.post(f"{BASE}/jobs/createTask", headers=_h(), json={"model": model, "input": inp})
                d = r.json()
            except (httpx.HTTPError, ValueError) as e:
                if attempt == 2:
                    raise KieError(f"сеть: {type(e).__name__}")
                await asyncio.sleep(2 + 2 * attempt)
                continue
            code = int(d.get("code") or r.status_code)
            if code == 200 and (d.get("data") or {}).get("taskId"):
                return d["data"]["taskId"]
            if code in (429, 500, 502, 503) and attempt < 2:
                await asyncio.sleep(3 + 3 * attempt)
                continue
            raise KieError(f"{code}: {d.get('msg') or d}"[:300])
    raise KieError("не удалось создать задачу")


async def create_sync(model: str, inp: dict) -> dict:
    """Endpoints that answer at once (e.g. Suno's timestamped lyrics): the whole reply, {} on a failure."""
    async with _client(60) as cl:
        r = await cl.post(f"{BASE}/jobs/createTask", headers=_h(), json={"model": model, "input": inp})
    try:
        d = r.json()
    except ValueError:
        return {}
    return d if int(d.get("code") or 0) == 200 else {}


async def status(task_id: str) -> dict:
    """Returns {'state': waiting|queuing|generating|success|fail, 'result': dict, 'error': str}."""
    async with _client(30) as cl:
        r = await cl.get(f"{BASE}/jobs/recordInfo", headers=_h(), params={"taskId": task_id})
        d = r.json()
    if int(d.get("code") or 0) != 200:
        raise KieError(f"{d.get('code')}: {d.get('msg')}")
    data = d.get("data") or {}
    res = data.get("response") or {}
    if not res and data.get("resultJson"):
        try:
            res = json.loads(data["resultJson"])
        except (TypeError, ValueError):
            res = {}
    return {"state": data.get("state", "waiting"), "result": res or {}, "error": data.get("failMsg") or data.get("failCode") or "",
            "credits": data.get("creditsConsumed")}


async def wait(task_id: str, on_tick=None, timeout: float = 1500, every: float = 5) -> dict:
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    errors = 0
    while loop.time() - t0 < timeout:
        try:
            st = await status(task_id)
            errors = 0
        except (KieError, httpx.HTTPError, ValueError) as e:
            errors += 1
            if errors >= 6:
                raise KieError(f"нет ответа о задаче: {e}")
            await asyncio.sleep(every)
            continue
        if on_tick:
            await on_tick(st["state"], loop.time() - t0)
        if st["state"] in ("success", "fail") and st.get("credits"):
            from . import costs
            costs.kie(st["credits"], f"kie task {task_id}")
        if st["state"] == "success":
            return st["result"]
        if st["state"] == "fail":
            raise KieError(st["error"] or "генерация не удалась")
        await asyncio.sleep(every)
    raise KieError("слишком долго, попробуйте ещё раз")
