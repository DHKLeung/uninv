"""Broker accounts and positions data store."""

from uninv_backend.models import AccountMetadata, Broker, Position

BROKERS: list[Broker] = [
    Broker(id="ibkr-hk", name="Interactive Brokers (Hong Kong)"),
    Broker(id="futubull-hk", name="Futubull (Hong Kong)"),
]

ACCOUNTS: dict[str, list[AccountMetadata]] = {
    "ibkr-hk": [
        AccountMetadata(
            account_id="U16110728",
            broker_id="ibkr-hk",
            alias="IBKR-HK (0728)",
        ),
    ],
    "futubull-hk": [
        AccountMetadata(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            alias="Futubull-HK (7283)",
        ),
        AccountMetadata(
            account_id="1001281798927612",
            broker_id="futubull-hk",
            alias="Futubull-HK (7612)",
        ),
        AccountMetadata(
            account_id="1001272756530281",
            broker_id="futubull-hk",
            alias="Futubull-HK (0281)",
        ),
    ],
}

# Rich set of mock positions across Stocks, ETFs, Futures, Options,
# Futures Options, and Bitcoin (all USD)
POSITIONS: dict[str, list[Position]] = {
    "ibkr-hk": [
        # Stock: Apple Inc.
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="Apple Inc.",
            symbol="AAPL",
            position=150.0,
            average_price=215.40,
            mark_price=228.50,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Stock: NVIDIA Corp.
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="NVIDIA Corporation",
            symbol="NVDA",
            position=80.0,
            average_price=118.20,
            mark_price=135.60,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Futures: E-mini S&P 500 Mar 19 '27 (has delivery_date, no expiry_date, multiplier = 50)
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="E-mini S&P 500 Mar 19 '27",
            symbol="ESH27",
            position=2.0,
            average_price=5850.00,
            mark_price=5925.00,
            currency="USD",
            expiry_date=None,
            delivery_date="2027-03-19",
            multiplier=50.0,
        ),
        # Stock Option: AAPL Dec 18 '26 240C (has expiry_date, no delivery_date, multiplier = 100)
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="AAPL Dec 18 '26 240C",
            symbol="AAPL261218C00240000",
            position=5.0,
            average_price=14.50,
            mark_price=18.20,
            currency="USD",
            expiry_date="2026-12-18",
            delivery_date=None,
            multiplier=100.0,
        ),
        # Futures Option: E-mini S&P 500 Mar 19 '27 7400P Dec 18 '26
        # (has expiry_date, no delivery_date, multiplier = 50)
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="E-mini S&P 500 Mar 19 '27 7400P Dec 18 '26",
            symbol="ESH27 7400P 261218",
            position=2.0,
            average_price=85.00,
            mark_price=92.50,
            currency="USD",
            expiry_date="2026-12-18",
            delivery_date=None,
            multiplier=50.0,
        ),
        # Crypto: Bitcoin
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="Bitcoin",
            symbol="BTC",
            position=1.25,
            average_price=68500.00,
            mark_price=71200.00,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
    ],
    "futubull-hk": [
        # Account 1: 1001279250287283 -> Futubull-HK (7283)
        # ETF: Invesco QQQ Trust
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="Invesco QQQ Trust Series 1",
            symbol="QQQ",
            position=200.0,
            average_price=470.00,
            mark_price=495.20,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Stock: Microsoft Corp.
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="Microsoft Corporation",
            symbol="MSFT",
            position=100.0,
            average_price=410.50,
            mark_price=425.00,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Stock Option: QQQ Dec 18 '26 460P (short 2 contracts, multiplier = 100)
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="QQQ Dec 18 '26 460P",
            symbol="QQQ261218P00460000",
            position=-2.0,
            average_price=12.00,
            mark_price=9.80,
            currency="USD",
            expiry_date="2026-12-18",
            delivery_date=None,
            multiplier=100.0,
        ),
        # Account 2: 1001281798927612 -> Futubull-HK (7612)
        # ETF: SPDR S&P 500 ETF Trust
        Position(
            account_id="1001281798927612",
            broker_id="futubull-hk",
            instrument="SPDR S&P 500 ETF Trust",
            symbol="SPY",
            position=120.0,
            average_price=565.00,
            mark_price=585.40,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Stock: Alphabet Inc.
        Position(
            account_id="1001281798927612",
            broker_id="futubull-hk",
            instrument="Alphabet Inc. Class A",
            symbol="GOOGL",
            position=75.0,
            average_price=162.00,
            mark_price=178.50,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Futures: E-mini Nasdaq 100 Mar 19 '27 (has delivery_date, no expiry_date, multiplier = 20)
        Position(
            account_id="1001281798927612",
            broker_id="futubull-hk",
            instrument="E-mini Nasdaq 100 Mar 19 '27",
            symbol="NQH27",
            position=1.0,
            average_price=20400.00,
            mark_price=20750.00,
            currency="USD",
            expiry_date=None,
            delivery_date="2027-03-19",
            multiplier=20.0,
        ),
        # Account 3: 1001272756530281 -> Futubull-HK (0281)
        # Stock: Amazon.com Inc.
        Position(
            account_id="1001272756530281",
            broker_id="futubull-hk",
            instrument="Amazon.com Inc.",
            symbol="AMZN",
            position=90.0,
            average_price=185.00,
            mark_price=198.40,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Stock: Tesla Inc.
        Position(
            account_id="1001272756530281",
            broker_id="futubull-hk",
            instrument="Tesla Inc.",
            symbol="TSLA",
            position=60.0,
            average_price=240.00,
            mark_price=265.50,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Stock Option: TSLA Dec 18 '26 280C (multiplier = 100)
        Position(
            account_id="1001272756530281",
            broker_id="futubull-hk",
            instrument="TSLA Dec 18 '26 280C",
            symbol="TSLA261218C00280000",
            position=3.0,
            average_price=22.00,
            mark_price=27.50,
            currency="USD",
            expiry_date="2026-12-18",
            delivery_date=None,
            multiplier=100.0,
        ),
        # Crypto: Bitcoin
        Position(
            account_id="1001272756530281",
            broker_id="futubull-hk",
            instrument="Bitcoin",
            symbol="BTC",
            position=0.5,
            average_price=65200.00,
            mark_price=71200.00,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
    ],
}
