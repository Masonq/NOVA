import asyncio
from test_core import login, A
from app.config import get_settings


@A
async def test_costs_are_recorded_and_shown(client, monkeypatch):
    from app import costs, kie
    monkeypatch.setattr(get_settings(), "admin_tg_ids", "6601")
    ha = await login(client, 6601)
    costs.set_ctx(kind="image", job_id=None, user_id=None)
    costs.openrouter({"usage": {"cost": 0.035}}, "seedream")          # cost in the reply
    costs.kie(14, "suno")                                               # Kie credits -> $0.07
    costs.set_ctx(kind="chat")
    costs.openrouter({"usage": {"cost": 0.002}}, "chat")
    await asyncio.sleep(0.3)
    st = (await client.get("/api/admin/stats", headers=ha)).json()
    assert abs(st["money"]["cost_usd"] - 0.11) < 0.005
    assert abs(st["costs"]["by_kind"]["image"] - 0.105) < 0.001 and abs(st["costs"]["by_kind"]["chat"] - 0.002) < 0.0005
    assert abs(st["costs"]["by_provider"]["kie"] - 0.07) < 0.0001
    assert st["balances"]["kie"]["credits"] == 1080 and st["balances"]["openrouter"]["key_limit"] == 5


@A
async def test_kie_wait_records_credits(monkeypatch):
    from app import kie, costs
    seen = []
    monkeypatch.setattr(costs, "kie", lambda c, note="": seen.append(c))
    async def status(task):
        return {"state": "success", "result": {"resultUrls": ["u"]}, "error": "", "credits": 50}
    monkeypatch.setattr(kie, "status", status)
    assert (await kie.wait("t1", None, timeout=5, every=0.01))["resultUrls"] == ["u"] and seen == [50]
