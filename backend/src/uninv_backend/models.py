"""Shared data models.

These Pydantic models are the contract between broker connectors, the aggregation layer
and the desktop app. Broker connectors translate whatever their broker returns into
`Account` and `Position`; everything downstream only ever sees these types.

Money values are plain floats for now (fine for display). If we start doing accounting
(e.g. tax lots, realised P&L), switch to `Decimal`.
"""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

# --------------------------------------------------------------------------------------
# Broker-level data (what a connector returns)
# --------------------------------------------------------------------------------------


class AssetClass(StrEnum):
    STOCK = "stock"
    ETF = "etf"
    OPTION = "option"
    BOND = "bond"
    FUND = "fund"
    CRYPTO = "crypto"
    CASH = "cash"


class OptionRight(StrEnum):
    CALL = "call"
    PUT = "put"


class OptionDetails(BaseModel):
    """Contract details for option positions (used later by the strategy builder)."""

    underlying: str
    right: OptionRight
    strike: float
    expiry: date


class Broker(BaseModel):
    id: str = Field(description="Stable short id, e.g. 'ibkr'.")
    name: str
    is_simulated: bool = Field(description="True when data is hardcoded/mock, not a real API.")


class Account(BaseModel):
    id: str = Field(description="Globally unique account id, e.g. 'ibkr-U1234567'.")
    broker_id: str
    name: str
    account_type: str = Field(description="e.g. 'margin', 'cash', 'ira'.")
    currency: str = Field(description="Account base currency (ISO 4217).")
    cash_balance: float = Field(description="Cash in the account currency.")


class Position(BaseModel):
    """A holding exactly as reported by a broker, in the instrument's own currency."""

    account_id: str
    broker_id: str
    symbol: str
    name: str
    asset_class: AssetClass
    quantity: float = Field(description="Negative for short positions.")
    average_cost: float = Field(description="Average cost per unit (before multiplier).")
    market_price: float = Field(description="Latest price per unit (before multiplier).")
    currency: str
    multiplier: float = Field(default=1, description="Contract multiplier, e.g. 100 for options.")
    option: OptionDetails | None = None

    @computed_field
    @property
    def id(self) -> str:
        """Unique position id, used to reference positions from groups."""
        return f"{self.account_id}:{self.symbol}"

    @computed_field
    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price * self.multiplier

    @computed_field
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.average_cost * self.multiplier

    @computed_field
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis


# --------------------------------------------------------------------------------------
# User-defined grouping
# --------------------------------------------------------------------------------------


class PositionGroup(BaseModel):
    """A user-defined set of positions (can span brokers; a position can be in many groups)."""

    id: str
    name: str
    description: str = ""
    color: str = Field(default="#888888", description="Hex color used by the UI.")
    position_ids: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------------------
# Unified portfolio view (what the API returns to the desktop app)
# --------------------------------------------------------------------------------------


class PositionView(Position):
    """A position enriched with base-currency values and portfolio context."""

    fx_rate: float = Field(description="Multiply instrument-currency values by this to get base.")
    market_value_base: float
    cost_basis_base: float
    unrealized_pnl_base: float
    unrealized_pnl_pct: float = Field(description="Fraction, 0.12 = +12%.")
    weight: float = Field(description="Fraction of total net liquidation value.")
    group_ids: list[str] = Field(default_factory=list)


class AllocationSlice(BaseModel):
    """One slice of an allocation breakdown (by asset class, currency, group, symbol...)."""

    key: str
    label: str
    market_value: float = Field(description="In base currency.")
    unrealized_pnl: float = Field(description="In base currency.")
    weight: float = Field(description="Fraction of total net liquidation value.")
    position_count: int
    color: str | None = None


class AccountSummary(BaseModel):
    account: Account
    broker_name: str
    positions_value: float = Field(description="In base currency.")
    cash: float = Field(description="In base currency.")
    net_liquidation: float = Field(description="positions_value + cash, in base currency.")
    unrealized_pnl: float = Field(description="In base currency.")
    weight: float
    position_count: int


class PortfolioTotals(BaseModel):
    positions_value: float
    cash: float
    net_liquidation: float
    cost_basis: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class BrokerError(BaseModel):
    """Reported when a broker fails, so one broken connection doesn't hide the whole portfolio."""

    broker_id: str
    message: str


class PortfolioSummary(BaseModel):
    base_currency: str
    as_of: datetime
    totals: PortfolioTotals
    brokers: list[Broker]
    accounts: list[AccountSummary]
    by_asset_class: list[AllocationSlice]
    by_currency: list[AllocationSlice]
    by_symbol: list[AllocationSlice] = Field(
        description="Holdings consolidated across all accounts (e.g. MSFT held at two brokers)."
    )
    groups: list[AllocationSlice] = Field(
        description="Per-group totals. Groups can overlap, so weights need not sum to 1."
    )
    positions: list[PositionView]
    errors: list[BrokerError] = Field(default_factory=list)
