from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(get_settings().database_url, pool_size=10, max_overflow=10, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with Session() as s:
        yield s


async def init_db():
    from . import models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # additive columns for databases created by earlier versions
        from sqlalchemy import text
        for stmt in ("ALTER TABLE users ADD COLUMN IF NOT EXISTS agent_voice VARCHAR(32) NOT NULL DEFAULT 'Sulafat'",
                     "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS channel VARCHAR(8) NOT NULL DEFAULT 'chat'",
                     "CREATE INDEX IF NOT EXISTS ix_chat_messages_channel ON chat_messages (channel)",
                     "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS moderation VARCHAR(300) NOT NULL DEFAULT ''"):
            await conn.execute(text(stmt))
