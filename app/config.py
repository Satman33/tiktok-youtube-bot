from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    BOT_TOKEN: str = ""
    DATABASE_URL: str = "sqlite+aiosqlite:///botdb.sqlite"
    REDIS_URL: str = "redis://localhost:6379"

    TELEGRAM_MAX_SIZE: int = 50 * 1024 * 1024  # 50MB
    DAILY_LIMIT: int = 5

    YTDLP_COOKIES_PATH: str = "cookies.txt"

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = False

    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
