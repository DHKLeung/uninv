"""Simulated brokers that return hardcoded data.

These let us build the unified portfolio view before any real broker is connected.
Prices and account numbers are made up for illustration; they are not real quotes.
When a real connector exists for a broker, replace its mock in `registry.py`.
"""

from datetime import date

from uninv_backend.brokers.base import BrokerConnector
from uninv_backend.models import (
    Account,
    AssetClass,
    Broker,
    OptionDetails,
    OptionRight,
    Position,
)


class MockBroker(BrokerConnector):
    """A broker whose accounts and positions are supplied up front."""

    def __init__(self, info: Broker, accounts: list[Account], positions: list[Position]) -> None:
        self._info = info
        self._accounts = accounts
        self._positions = positions

    @property
    def info(self) -> Broker:
        return self._info

    async def get_accounts(self) -> list[Account]:
        return list(self._accounts)

    async def get_positions(self) -> list[Position]:
        return list(self._positions)


def _pos(
    account: Account,
    symbol: str,
    name: str,
    asset_class: AssetClass,
    quantity: float,
    average_cost: float,
    market_price: float,
    currency: str | None = None,
    **extra,
) -> Position:
    """Small helper to keep the hardcoded data below readable."""
    return Position(
        account_id=account.id,
        broker_id=account.broker_id,
        symbol=symbol,
        name=name,
        asset_class=asset_class,
        quantity=quantity,
        average_cost=average_cost,
        market_price=market_price,
        currency=currency or account.currency,
        **extra,
    )


# --------------------------------------------------------------------------------------
# Interactive Brokers (simulated): one USD margin account, includes an option position.
# --------------------------------------------------------------------------------------


def mock_ibkr() -> MockBroker:
    info = Broker(id="ibkr", name="Interactive Brokers", is_simulated=True)
    acct = Account(
        id="ibkr-U1234567",
        broker_id=info.id,
        name="IBKR Margin",
        account_type="margin",
        currency="USD",
        cash_balance=12_500.00,
    )
    positions = [
        _pos(acct, "VOO", "Vanguard S&P 500 ETF", AssetClass.ETF, 40, 410.00, 545.20),
        _pos(acct, "AAPL", "Apple Inc.", AssetClass.STOCK, 50, 150.00, 228.50),
        _pos(acct, "MSFT", "Microsoft Corp.", AssetClass.STOCK, 25, 310.00, 430.10),
        _pos(acct, "NVDA", "NVIDIA Corp.", AssetClass.STOCK, 60, 45.00, 140.30),
        _pos(acct, "TLT", "iShares 20+ Year Treasury Bond ETF", AssetClass.BOND, 100, 95.00, 88.40),
        _pos(
            acct,
            "AAPL270115C00250000",
            "AAPL Jan 15 '27 250 Call",
            AssetClass.OPTION,
            2,
            8.50,
            12.30,
            multiplier=100,
            option=OptionDetails(
                underlying="AAPL",
                right=OptionRight.CALL,
                strike=250,
                expiry=date(2027, 1, 15),
            ),
        ),
    ]
    return MockBroker(info, [acct], positions)


# --------------------------------------------------------------------------------------
# Futu (simulated): HKD account holding HK stocks plus one US stock (multi-currency).
# --------------------------------------------------------------------------------------


def mock_futu() -> MockBroker:
    info = Broker(id="futu", name="Futu", is_simulated=True)
    acct = Account(
        id="futu-HK001",
        broker_id=info.id,
        name="Futu Securities",
        account_type="margin",
        currency="HKD",
        cash_balance=30_000.00,
    )
    positions = [
        _pos(acct, "0700.HK", "Tencent Holdings", AssetClass.STOCK, 300, 320.00, 410.60),
        _pos(acct, "2800.HK", "Tracker Fund of Hong Kong", AssetClass.ETF, 2000, 18.50, 21.20),
        _pos(acct, "9988.HK", "Alibaba Group", AssetClass.STOCK, 400, 85.00, 118.40),
        _pos(acct, "TSLA", "Tesla Inc.", AssetClass.STOCK, 10, 220.00, 250.80, currency="USD"),
    ]
    return MockBroker(info, [acct], positions)


# --------------------------------------------------------------------------------------
# Charles Schwab (simulated): two accounts (IRA + brokerage). MSFT is also held at IBKR,
# which shows consolidation across brokers.
# --------------------------------------------------------------------------------------


def mock_schwab() -> MockBroker:
    info = Broker(id="schwab", name="Charles Schwab", is_simulated=True)
    ira = Account(
        id="schwab-IRA-4821",
        broker_id=info.id,
        name="Schwab Roth IRA",
        account_type="ira",
        currency="USD",
        cash_balance=3_000.00,
    )
    brokerage = Account(
        id="schwab-BRK-9917",
        broker_id=info.id,
        name="Schwab Individual",
        account_type="cash",
        currency="USD",
        cash_balance=5_250.00,
    )
    positions = [
        _pos(ira, "VTI", "Vanguard Total Stock Market ETF", AssetClass.ETF, 80, 200.00, 285.40),
        _pos(ira, "SCHD", "Schwab US Dividend Equity ETF", AssetClass.ETF, 150, 70.00, 80.15),
        _pos(ira, "BND", "Vanguard Total Bond Market ETF", AssetClass.BOND, 120, 74.00, 72.30),
        _pos(brokerage, "GOOGL", "Alphabet Inc. Class A", AssetClass.STOCK, 30, 120.00, 175.60),
        _pos(brokerage, "AMZN", "Amazon.com Inc.", AssetClass.STOCK, 20, 130.00, 195.25),
        _pos(brokerage, "MSFT", "Microsoft Corp.", AssetClass.STOCK, 10, 380.00, 430.10),
    ]
    return MockBroker(info, [ira, brokerage], positions)
