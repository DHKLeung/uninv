"""Shared data models for uninv.

Professional Pydantic v2 data models for brokers, accounts, and positions.
"""

from pydantic import BaseModel, Field, computed_field


class Broker(BaseModel):
    """Broker metadata."""

    id: str = Field(description="Broker identifier, e.g. 'ibkr-hk'")
    name: str = Field(description="Broker display name")


class AccountMetadata(BaseModel):
    """Account metadata under a broker."""

    account_id: str = Field(description="Broker account number, e.g. 'U16110728'")
    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr-hk'")
    alias: str = Field(description="Display alias, e.g. 'IBKR-HK(0728)'")


class Position(BaseModel):
    """Holding position as reported by a broker.

    Required fields:
      - instrument
      - symbol
      - position (quantity)
      - average_price
      - mark_price
      - currency
      - expiry_date (for options and futures)
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
    multiplier: float = 1.0

    @computed_field
    @property
    def market_value(self) -> float:
        return round(self.position * self.mark_price * self.multiplier, 2)

    @computed_field
    @property
    def cost_basis(self) -> float:
        return round(self.position * self.average_price * self.multiplier, 2)

    @computed_field
    @property
    def unrealised_pnl(self) -> float:
        return round(self.market_value - self.cost_basis, 2)

    @computed_field
    @property
    def unrealised_pnl_pct(self) -> float:
        if abs(self.cost_basis) < 1e-6:
            return 0.0
        return round(self.unrealised_pnl / abs(self.cost_basis), 4)
