"""Shared data models for uninv backend.

Standardized broker models with strict Enums for loud failure on new symbols,
exchanges, security types, or currencies.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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


class SecurityType(StrEnum):
    """Standardized security types."""

    STOCKS = "STOCKS"
    OPTIONS = "OPTIONS"
    FUTURES = "FUTURES"
    FUTURES_OPTIONS = "FUTURES_OPTIONS"
    CRYPTO = "CRYPTO"
    CASH = "CASH"


class OptionType(StrEnum):
    """Option contract right."""

    CALL = "CALL"
    PUT = "PUT"


class SupportingBroker(BaseModel):
    """Supported broker."""

    id: str = Field(description="Broker identifier, e.g. 'ibkr'")
    name: str = Field(description="Broker display name")


class AccountsResponse(BaseModel):
    """List of account IDs for a broker with acquisition timestamp."""

    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr'")
    asof: datetime = Field(description="UTC timestamp of the query (ISO 8601)")
    accounts: list[str] = Field(description="List of managed account IDs")


class CashBalanceItem(BaseModel):
    """Cash balance in a specific non-BASE currency."""

    currency: Currency = Field(description="Explicit currency")
    amount: float = Field(description="Cash amount in this currency")


class AccountValues(BaseModel):
    """Key raw account margins and cash balances (all non-BASE, explicit currency)."""

    currency: Currency = Field(description="Account base currency, e.g. Currency.USD")
    available_funds: float = Field(description="Available funds for trading")
    buying_power: float = Field(description="Total buying power")
    cash_balance: float = Field(description="Total cash balance in account base currency")
    cash_balances: list[CashBalanceItem] = Field(
        default_factory=list,
        description="Cash balance breakdown by individual non-BASE currency",
    )
    equity_with_loan_value: float = Field(description="Equity with loan value")
    excess_liquidity: float = Field(description="Excess liquidity")
    gross_position_value: float = Field(description="Gross position value")
    init_margin_req: float = Field(description="Initial margin requirement")
    maint_margin_req: float = Field(description="Maintenance margin requirement")
    net_liquidation: float = Field(description="Net liquidation value")
    unrealized_pnl: float = Field(description="Total account unrealized P&L")


class Position(BaseModel):
    """Standardized holding position with backend-calculated cost basis and API market values."""

    instrument: str = Field(
        description="Descriptive instrument name (e.g. 'NVDA Jan19'29 145 CALL')"
    )
    symbol: str = Field(description="Contract local symbol, e.g. 'BOXX', 'EW3Z6 P7400'")
    position: float = Field(description="Quantity held (positive for long, negative for short)")
    avg_price: float = Field(description="Unit entry price / normalized average cost")
    mark_price: float = Field(description="Current unit market price")
    cost_basis: float = Field(description="Total cost basis = position * avg_price * multiplier")
    market_value: float = Field(description="Market value from broker portfolio feed")
    unrealized_pnl: float = Field(description="Unrealized P&L from broker portfolio feed")
    multiplier: float = Field(default=1.0, description="Contract multiplier")
    currency: Currency = Field(description="Trading currency")
    exchange: Exchange | None = Field(default=None, description="Primary exchange")
    sec_type: SecurityType = Field(description="Standardized security type")
    last_trade_date: str | None = Field(
        default=None, description="Last trading date / expiration in YYYY-MM-DD format"
    )
    strike: float | None = Field(default=None, description="Option/future option strike price")
    option_type: OptionType | None = Field(default=None, description="Option type (CALL or PUT)")


class BrokerAccountSnapshot(BaseModel):
    """Complete account snapshot combining account values and open positions."""

    broker_id: str = Field(description="Broker identifier, e.g. 'ibkr'")
    account_id: str = Field(description="Broker account identifier, e.g. 'U16110728'")
    asof: datetime = Field(description="UTC timestamp of the query (ISO 8601)")
    account_values: AccountValues = Field(description="Account-wide margins and cash balances")
    positions: list[Position] = Field(default_factory=list, description="Open positions")


class FxRate(BaseModel):
    """Foreign exchange rate quote."""

    base: Currency = Field(description="Base currency")
    quote: Currency = Field(description="Quote currency")
    rate: float = Field(description="Units of quote per 1 unit of base")
    asof: datetime = Field(description="UTC timestamp of the query (ISO 8601)")


# Backwards compatibility alias
Broker = SupportingBroker
