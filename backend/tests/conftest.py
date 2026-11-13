import os, sys, tempfile
os.environ.update(DATABASE_URL="postgresql+asyncpg://nova:nova@127.0.0.1:5432/nova_test", BOT_TOKEN="123:TEST",
                  JWT_SECRET="t"*40, WEBHOOK_SECRET="wh", OPENROUTER_KEY="x",
                  STORAGE_DIR=tempfile.mkdtemp(), STATIC_DIR=tempfile.mkdtemp(), PUBLIC_URL="https://nova.test")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest, pytest_asyncio, httpx
from sqlalchemy import text

@pytest_asyncio.fixture(loop_scope="session", scope="session", autouse=True)
async def _schema():
    from app.db import engine, Base, init_db
    from app import models  # noqa
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.drop_all)
    await init_db()
    yield
    await engine.dispose()

@pytest_asyncio.fixture(loop_scope="session")
async def client():
    from app.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        yield c


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """The bot and the prompt enhancer never go to the internet in tests; a test may override them."""
    from app import bot, ai
    async def same(prompt, style="", has_ref=False): return prompt
    monkeypatch.setattr(ai, "enhance_prompt", same)
    async def brief(prompt, genre="", mood="", vocal=False):
        return {"style": ", ".join(x for x in (genre, mood) if x), "title": "", "idea": prompt}
    monkeypatch.setattr(ai, "music_brief", brief)
    sent = []
    async def send(chat_id, text, markup=None):
        sent.append((chat_id, text)); return {"ok": True}
    async def call(method, payload):
        sent.append((method, payload)); return {"ok": True, "result": "https://t.me/$x"}
    monkeypatch.setattr(bot, "send", send)
    monkeypatch.setattr(bot, "call", call)
    return sent



@pytest.fixture(autouse=True)
def round_test_prices(monkeypatch):
    """Older tests were written with 300 welcome credits and +100 for a friend; the real defaults are checked in test_prices."""
    from app import pricing
    monkeypatch.setitem(pricing.DEFAULT_PRICE, "welcome", 300)
    monkeypatch.setitem(pricing.DEFAULT_PRICE, "ref_friend", 100)
    pricing._loaded = 0
