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

    # Browser origins allowed to call the API directly. Defaults to allowing all
    # origins during development so mobile devices and web browsers on LAN can connect.
    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
