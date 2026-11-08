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

    # Interactive Brokers (TWS) connection settings
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7496
    ibkr_client_id: int = 99
    ibkr_timeout: float = 2.0

    # Futu OpenD connection settings
    futu_host: str = "127.0.0.1"
    futu_port: int = 11111
    futu_timeout: float = 3.0


@lru_cache
def get_settings() -> Settings:
    return Settings()


def update_broker_gateway(broker_id: str, host: str | None = None, port: int | None = None) -> None:
    """Dynamically update configured gateway host and/or port for a broker."""
    settings = get_settings()
    if broker_id == "ibkr":
        if host:
            settings.ibkr_host = host.strip()
        if port:
            settings.ibkr_port = port
    elif broker_id == "futu":
        if host:
            settings.futu_host = host.strip()
        if port:
            settings.futu_port = port
