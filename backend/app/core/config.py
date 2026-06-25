from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "舆情智析平台"
    api_prefix: str = "/api"
    database_url: str | None = "sqlite:///./opinion_sentinel.db"
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "opinion_sentinel"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    storage_root: Path = Path("./storage")
    analysis_poll_seconds: float = 2.0
    ai_request_timeout_seconds: float = 180.0
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
