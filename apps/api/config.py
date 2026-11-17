from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    next_public_supabase_url: str = ""
    next_public_supabase_publishable_key: str = ""
    supabase_jwt_secret: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""
    token_encryption_key: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_api_key: str = ""
    studio_max_runs_per_hour: int = 6
    darkforge_core_path: str = ""
    darkforge_history_path: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    web_origin: str = "http://127.0.0.1:3000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
