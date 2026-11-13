import os, sys, tempfile
os.environ.update(DATABASE_URL="postgresql+asyncpg://nova:nova@127.0.0.1:5432/nova_test", BOT_TOKEN="123:TEST",
                  JWT_SECRET="t"*40, WEBHOOK_SECRET="wh", GEMINI_KEY="x",
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
