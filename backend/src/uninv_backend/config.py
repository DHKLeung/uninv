"""Application settings.

Every field can be overridden with an environment variable prefixed with ``UNINV_``
(e.g. ``UNINV_PORT=9000``) or through a ``.env`` file in the working directory.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="UNINV_", env_file=".env", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8000

    # Currency that every portfolio total is converted into.
    base_currency: str = "USD"

    # Browser origins allowed to call the API directly. The Tauri app does not need this
    # (its requests go through Rust), but it lets you open the frontend in a normal browser
    # (served on port 1420) while iterating on the UI.
    cors_origins: list[str] = ["http://localhost:1420", "http://127.0.0.1:1420"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
