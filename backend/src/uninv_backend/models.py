"""Shared data models for uninv backend.

Standardized broker models with strict Enums for loud failure on new symbols,
exchanges, security types, or currencies.
All string fields are automatically normalized (leading/trailing whitespace stripped,
consecutive whitespace collapsed to 1 space).
Numerical fields preserve exact raw broker values without rounding.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class UninvModel(BaseModel):
    """Base model that normalizes all string fields to single-space, stripped strings."""

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_strings(cls, v: Any) -> Any:
        if isinstance(v, str):
            return " ".join(v.split())
        if isinstance(v, list):
            return [" ".join(x.split()) if isinstance(x, str) else x for x in v]
        return v


class Currency(StrEnum):
    """Standardized currency identifiers."""

    USD = "USD"
    HKD = "HKD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"
    CHF = "CHF"
    CNH = "CNH"
    SGD = "SGD"
    NZD = "NZD"


class Exchange(StrEnum):
    """Standardized trading exchanges."""

    BATS = "BATS"
    ARCA = "ARCA"
    NASDAQ = "NASDAQ"
    AMEX = "AMEX"
    NYSE = "NYSE"
    CME = "CME"
    OSL = "OSL"
    IDEALPRO = "IDEALPRO"
    NYMEX = "NYMEX"
    CBOT = "CBOT"
    COMEX = "COMEX"
    CBOE = "CBOE"
    SEHK = "SEHK"
    SSE = "SSE"
    SZSE = "SZSE"


class SecurityType(StrEnum):
    """Standardized security types."""

    STOCKS = "STOCKS"
    OPTIONS = "OPTIONS"
    FUTURES = "FUTURES"
    FUTURES_OPTIONS = "FUTURES OPTIONS"
    CRYPTO = "CRYPTO"
    CASH = "CASH"
    FUNDS = "FUNDS"
    BONDS = "BONDS"


class OptionType(StrEnum):
    """Option contract right."""

    CALL = "CALL"
    PUT = "PUT"


class SupportingBroker(UninvModel):
    """Supported broker."""

    id: str = Field(description="Broker identifier, e.g. 'ibkr'")
    name: str = Field(description="Broker display name")


class AccountsResponse(UninvModel):
    """List of account IDs for a broker with acquisition timestamp."""

    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr'")
    asof: datetime = Field(description="UTC timestamp of the query (ISO 8601)")
    accounts: list[str] = Field(description="List of managed account IDs")


class CashBalanceItem(UninvModel):
    """Cash balance in a specific non-BASE currency."""

    currency: Currency = Field(description="Explicit currency")
    amount: float = Field(description="Cash amount in this currency")


class AccountValues(UninvModel):
    """Key raw account margins and cash balances (all non-BASE, explicit currency)."""

    currency: Currency = Field(description="Account base currency, e.g. Currency.USD")
    net_liquidation: float = Field(description="Net liquidation value / Total assets")
    gross_position_value: float = Field(description="Gross position value")
    cash_balance: float = Field(
        default=0.0,
        description="Total cash balance in base currency (net_liquidation - gross_position_value)",
    )
    maint_margin_req: float = Field(description="Maintenance margin requirement")
    excess_liquidity: float = Field(
        description="Excess liquidity cushion (net_liquidation - maint_margin_req)"
    )
    unrealized_pnl: float = Field(description="Total account unrealized P&L")
    cash_balances: list[CashBalanceItem] = Field(
        default_factory=list,
        description="Cash balance breakdown by individual non-BASE currency",
    )


class Position(UninvModel):
    """Standardized holding position with backend-calculated cost basis and API market values.

    All numerical fields preserve exact raw broker numbers without display rounding.
    All string fields are guarded to contain no more than 1 consecutive space.
    """

    instrument: str = Field(
        description="Descriptive instrument name (e.g. 'NVDA Jan19'29 145 CALL', 'Fund Assets')"
    )
    symbol: str | None = Field(
        default=None, description="Contract local symbol, e.g. 'BOXX', 'NVDA 290119C00145000'"
    )
    position: float = Field(description="Quantity held (positive for long, negative for short)")
    avg_price: float | None = Field(
        default=None, description="Unit entry price / normalized average cost (raw float)"
    )
    mark_price: float = Field(description="Current unit market price (raw float)")
    cost_basis: float | None = Field(
        default=None, description="Total cost basis = position * avg_price * multiplier (raw float)"
    )
    market_value: float = Field(description="Market value from broker portfolio feed (raw float)")
    unrealized_pnl: float = Field(
        default=0.0, description="Unrealized P&L from broker portfolio feed (raw float)"
    )
    multiplier: float = Field(default=1.0, description="Contract multiplier")
    currency: Currency = Field(description="Trading currency")
    exchange: Exchange | None = Field(default=None, description="Primary exchange")
    sec_type: SecurityType = Field(description="Standardized security type")
    last_trading_date: str | None = Field(
        default=None, description="Last trading date / expiration in YYYY-MM-DD format"
    )
    strike: float | None = Field(default=None, description="Option/future option strike price")
    option_type: OptionType | None = Field(default=None, description="Option type (CALL or PUT)")


class BrokerConnectionTestResponse(UninvModel):
    """Result of testing connection to a broker gateway."""

    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr' or 'futu'")
    connected: bool = Field(description="Whether the broker gateway is reachable")
    message: str = Field(description="Status description or error message")


class BrokerGatewayConfig(UninvModel):
    """Configuration for a broker gateway."""

    host: str = Field(default="127.0.0.1", description="Gateway host or IP address")
    port: int = Field(description="Gateway TCP port", ge=1, le=65535)


class BrokerGatewayConfigRequest(UninvModel):
    """Request to update broker gateway configuration."""

    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr' or 'futu'")
    host: str | None = Field(default=None, description="Gateway host or IP address")
    port: int | None = Field(default=None, description="Gateway TCP port", ge=1, le=65535)


class BrokerGatewayConfigResponse(UninvModel):
    """Current configured gateways for all brokers."""

    status: str = Field(default="ok")
    gateways: dict[str, BrokerGatewayConfig] = Field(description="Configured gateways by broker ID")


class BrokerAccountSnapshot(UninvModel):
    """Complete account snapshot combining account values and open positions."""

    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr'")
    account_id: str = Field(description="Broker account identifier, e.g. 'U16110728'")
    asof: datetime = Field(description="UTC timestamp of the query (ISO 8601)")
    account_values: AccountValues = Field(description="Account-wide margins and cash balances")
    positions: list[Position] = Field(default_factory=list, description="Open positions")


class FxRate(UninvModel):
    """Foreign exchange rate quote preserving raw rate precision."""

    base: Currency = Field(description="Base currency")
    quote: Currency = Field(description="Quote currency")
    rate: float = Field(description="Units of quote per 1 unit of base (raw float)")
    asof: datetime = Field(description="UTC timestamp of the query (ISO 8601)")


class FxMatrixResponse(UninvModel):
    """Matrix of foreign exchange rates across all supported currencies."""

    asof: datetime = Field(description="UTC timestamp of the FX rates snapshot (ISO 8601)")
    currencies: list[Currency] = Field(description="List of all supported currency codes")
    rates: dict[Currency, dict[Currency, float]] = Field(
        description="Conversion matrix: rates[from][to] gives multiplier (1 from = X to)"
    )


# Backwards compatibility alias
Broker = SupportingBroker
