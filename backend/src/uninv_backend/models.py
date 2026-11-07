"""Shared data models for uninv backend.

Pure, non-derivable data models directly mapped from broker feeds.
All presentation, alias mapping, and derived calculations (market value,
cost basis, P&L, NLV) are left to client consumers.
"""

from pydantic import BaseModel, Field


class SupportingBroker(BaseModel):
    """Supported broker."""

    id: str = Field(description="Broker identifier, e.g. 'ibkr'")
    name: str = Field(description="Broker display name")


class CashBalanceItem(BaseModel):
    """Cash balance in a single specific currency."""

    currency: str = Field(description="Currency code, e.g. 'USD', 'HKD', 'GBP'")
    amount: float = Field(description="Total cash balance amount in this currency")


class AccountValues(BaseModel):
    """Key raw account margins and cash balances."""

    available_funds: float = Field(description="Available funds for trading")
    buying_power: float = Field(description="Total buying power")
    excess_liquidity: float = Field(description="Excess liquidity")
    maintenance_margin: float = Field(description="Maintenance margin requirement")
    currency: str = Field(default="USD", description="Default account currency")
    cash_balances: list[CashBalanceItem] = Field(
        default_factory=list,
        description="Cash balance breakdown by individual currency (excluding BASE)",
    )


class Position(BaseModel):
    """Raw holding position as reported by the broker without derived metrics.

    Derived values such as market value, cost basis, unrealised P&L, and
    P&L percentage can be calculated directly by the client:
      cost_basis = position * average_price * multiplier
      market_value = position * market_price * multiplier
      unrealized_pnl = (market_price - average_price) * position * multiplier
    """

    instrument: str = Field(description="Instrument full name or description")
    symbol: str = Field(description="Contract local symbol, e.g. 'BOXX', 'EW3Z6 P7400'")
    position: float = Field(description="Quantity held (positive for long, negative for short)")
    average_price: float = Field(description="Unit cost/entry price")
    market_price: float = Field(description="Current unit market price")
    multiplier: float = Field(default=1.0, description="Contract multiplier")
    currency: str = Field(description="Trading currency")
    primary_exchange: str | None = Field(
        default=None, description="Primary exchange or routing destination"
    )
    last_trading_date: str | None = Field(
        default=None, description="Last trading date / expiration (YYYYMMDD)"
    )
    sec_type: str | None = Field(
        default=None, description="Security type (e.g. 'STK', 'OPT', 'FOP', 'CRYPTO')"
    )
    strike: float | None = Field(default=None, description="Option/future option strike price")
    right: str | None = Field(default=None, description="Option right ('C' for Call, 'P' for Put)")
    underlying_symbol: str | None = Field(default=None, description="Underlying symbol")
    con_id: int | None = Field(default=None, description="Broker contract identifier")


# Backwards compatibility alias
Broker = SupportingBroker
