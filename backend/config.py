from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    app_env: str = "development"

    class Config:
        env_file = ".env"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
