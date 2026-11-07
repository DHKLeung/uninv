"""Shared data models for uninv.

Professional Pydantic v2 data models for brokers, accounts, and positions.
"""

from pydantic import BaseModel, Field


class Broker(BaseModel):
    """Broker metadata."""

    id: str = Field(description="Broker identifier, e.g. 'ibkr-hk'")
    name: str = Field(description="Broker display name")


class AccountMetadata(BaseModel):
    """Account metadata under a broker."""

    account_id: str = Field(description="Broker account number, e.g. 'U16110728'")
    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr-hk'")
    alias: str = Field(description="Display alias, e.g. 'IBKR-HK (0728)'")


class Position(BaseModel):
    """Raw holding position as reported by a broker.

    Derived metrics such as market value, cost basis, and unrealised P&L
    are calculated on the client side.
    """

    account_id: str
    broker_id: str
    instrument: str
    symbol: str
    position: float
    average_price: float
    mark_price: float
    currency: str = "USD"
    expiry_date: str | None = None
    delivery_date: str | None = None
    multiplier: float = 1.0
