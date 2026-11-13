from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")  # on the server systemd passes /opt/nova/.env

    bot_token: str = ""
    bot_username: str = "NovaAI_Agent"
    gemini_key: str = ""
    database_url: str = "postgresql+asyncpg://nova:nova@127.0.0.1:5432/nova"
    redis_url: str = "redis://127.0.0.1:6379/5"
    jwt_secret: str = "dev-secret-change-me"
    webhook_secret: str = "dev-webhook"
    public_url: str = "https://nova.89-208-113-147.sslip.io"
    storage_dir: str = "/opt/nova/storage"
    static_dir: str = "/opt/nova/frontend/dist"
    admin_tg_ids: str = ""

    welcome_credits: int = 300
    keep_days: int = 30
    remind_before_days: int = 3
    chat_daily_limit: int = 200

    chat_models: str = "gemini-3.8-flash,gemini-3.5-flash"


@lru_cache
def get_settings() -> Settings:
    return Settings()
