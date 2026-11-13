from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(128), default="")
    username: Mapped[str] = mapped_column(String(64), default="")
    balance: Mapped[int] = mapped_column(Integer, default=0)
    welcome_given: Mapped[bool] = mapped_column(Boolean, default=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    can_message: Mapped[bool] = mapped_column(Boolean, default=True)
    agent_voice: Mapped[str] = mapped_column(String(32), default="Sulafat", server_default="Sulafat")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Ledger(Base):
    """Every change of balance: grant, purchase, charge, refund."""
    __tablename__ = "ledger"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    delta: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(24))  # welcome | purchase | charge | refund | admin | promo
    title: Mapped[str] = mapped_column(String(200), default="")
    job_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Job(Base):
    """A generation: image, video, music, tts. Files expire after keep_days."""
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed|cancelled|expired
    prompt: Mapped[str] = mapped_column(Text, default="")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    model: Mapped[str] = mapped_column(String(64), default="")
    cost: Mapped[int] = mapped_column(Integer, default=0)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    stage: Mapped[str] = mapped_column(String(64), default="")
    files: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str] = mapped_column(Text, default="")
    favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | model
    channel: Mapped[str] = mapped_column(String(8), default="chat", server_default="chat", index=True)  # chat | agent
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Memory(Base):
    """Facts the agent remembers about the user. Kept until the user deletes them."""
    __tablename__ = "memories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LoginCode(Base):
    """Site / PWA login: the user confirms in the bot, the site polls."""
    __tablename__ = "login_codes"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


Index("ix_jobs_user_created", Job.user_id, Job.created_at.desc())
Index("ix_ledger_user_created", Ledger.user_id, Ledger.created_at.desc())
