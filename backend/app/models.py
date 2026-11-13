import secrets
from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, JSON
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
    referrer_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    ref_rewarded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
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
    status: Mapped[str] = mapped_column(String(16), default="queued")  # review|queued|running|done|failed|cancelled|rejected|expired
    moderation: Mapped[str] = mapped_column(String(300), default="", server_default="")
    dir_token: Mapped[str] = mapped_column(String(24), default=lambda: secrets.token_hex(8), server_default="")   # unguessable folder
    share_token: Mapped[str | None] = mapped_column(String(24), nullable=True, unique=True, index=True)
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
    device: Mapped[str] = mapped_column(String(80), default="", server_default="")     # «Chrome · Windows» of the computer
    ip: Mapped[str] = mapped_column(String(64), default="", server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


Index("ix_jobs_user_created", Job.user_id, Job.created_at.desc())
Index("ix_ledger_user_created", Ledger.user_id, Ledger.created_at.desc())


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(12))          # stars | crypto
    pack: Mapped[str] = mapped_column(String(16))
    credits: Mapped[int] = mapped_column(Integer)
    amount: Mapped[str] = mapped_column(String(24))          # "400" stars or "4.99" USD
    currency: Mapped[str] = mapped_column(String(8))         # XTR | USD
    payload: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)   # pending | paid | expired | refunded
    external_id: Mapped[str] = mapped_column(String(128), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PromoCode(Base):
    __tablename__ = "promo_codes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    credits: Mapped[int] = mapped_column(Integer)
    max_uses: Mapped[int] = mapped_column(Integer, default=100)
    used: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class PromoUse(Base):
    __tablename__ = "promo_uses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    promo_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("promo_id", "user_id"),)


class AdminLog(Base):
    __tablename__ = "admin_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(40))
    target: Mapped[str] = mapped_column(String(80), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


class Broadcast(Base):
    __tablename__ = "broadcasts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    button: Mapped[str] = mapped_column(String(40), default="")
    status: Mapped[str] = mapped_column(String(12), default="queued")   # queued | sending | done | cancelled
    total: Mapped[int] = mapped_column(Integer, default=0)
    sent: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
