"""Broker accounts, cash balances, and positions data store."""

from uninv_backend.models import AccountMetadata, Broker, CashBalance, Position

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

CASH_BALANCES: dict[str, list[CashBalance]] = {
    "ibkr-hk": [
        CashBalance(
            broker_id="ibkr-hk",
            account_id="U16110728",
            cash_balance=-6612.62,
            currency="USD",
        ),
    ],
    "futubull-hk": [
        CashBalance(
            broker_id="futubull-hk",
            account_id="1001279250287283",
            cash_balance=0.0,
            currency="USD",
        ),
        CashBalance(
            broker_id="futubull-hk",
            account_id="1001281798927612",
            cash_balance=0.0,
            currency="USD",
        ),
        CashBalance(
            broker_id="futubull-hk",
            account_id="1001272756530281",
            cash_balance=0.0,
            currency="USD",
        ),
    ],
}

# User-specified positions in IBKR-HK (U16110728)
POSITIONS: dict[str, list[Position]] = {
    "ibkr-hk": [
        # 1. BOXX: 463 pos, 118.95 mark, 115.58 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="Alpha Architect 1-3 Month Box ETF",
            symbol="BOXX",
            position=463.0,
            average_price=115.58,
            mark_price=118.95,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 2. BTC: 0.05981 pos, 75851.50 mark, 70729.40 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="Bitcoin",
            symbol="BTC",
            position=0.05981,
            average_price=70729.40,
            mark_price=75851.50,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 3. CTAP: 162 pos, 26.00 mark, 28.62 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="Capital Group Short Duration Municipal Income ETF",
            symbol="CTAP",
            position=162.0,
            average_price=28.62,
            mark_price=26.00,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 4. ESH27 7400P 261218: -1 pos, 169.41 mark, 90.97 avg (multiplier 50)
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="E-mini S&P 500 Mar 19 '27 7400 Put Dec 18 '26",
            symbol="ESH27 7400P 261218",
            position=-1.0,
            average_price=90.97,
            mark_price=169.41,
            currency="USD",
            expiry_date="2026-12-18",
            delivery_date=None,
            multiplier=50.0,
        ),
        # 5. GOOGL290119P00230000: 1 pos, 100.32 mark, 96.66 avg (multiplier 100)
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="GOOGL Jan 19 '29 230 Put",
            symbol="GOOGL290119P00230000",
            position=1.0,
            average_price=96.66,
            mark_price=100.32,
            currency="USD",
            expiry_date="2029-01-19",
            delivery_date=None,
            multiplier=100.0,
        ),
        # 6. MATE: 150 pos, 29.09 mark, 30.90 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="Roundhill MEME ETF",
            symbol="MATE",
            position=150.0,
            average_price=30.90,
            mark_price=29.09,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 7. NVDA290119C00145000: 1 pos, 73.38 mark, 70.82 avg (multiplier 100)
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="NVDA Jan 19 '29 145 Call",
            symbol="NVDA290119C00145000",
            position=1.0,
            average_price=70.82,
            mark_price=73.38,
            currency="USD",
            expiry_date="2029-01-19",
            delivery_date=None,
            multiplier=100.0,
        ),
        # 8. QLD: 111.13 pos, 74.36 mark, 78.64 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="ProShares Ultra QQQ",
            symbol="QLD",
            position=111.13,
            average_price=78.64,
            mark_price=74.36,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 9. RSST: 137 pos, 32.05 mark, 30.73 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="Return Stacked US Stocks & Futures Yield ETF",
            symbol="RSST",
            position=137.0,
            average_price=30.73,
            mark_price=32.05,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 10. SSO: 135.31 pos, 64.10 mark, 63.86 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="ProShares Ultra S&P500",
            symbol="SSO",
            position=135.31,
            average_price=63.86,
            mark_price=64.10,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 11. TQQQ: 73.62 pos, 52.40 mark, 59.39 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="ProShares UltraPro QQQ",
            symbol="TQQQ",
            position=73.62,
            average_price=59.39,
            mark_price=52.40,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 12. UPRO: 32.23 pos, 129.32 mark, 131.29 avg
        Position(
            account_id="U16110728",
            broker_id="ibkr-hk",
            instrument="ProShares UltraPro S&P500",
            symbol="UPRO",
            position=32.23,
            average_price=131.29,
            mark_price=129.32,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
    ],
    "futubull-hk": [
        # Account 1001279250287283 -> Futubull-HK (7283)
        # 1. ASML: 3 pos, 1425.91 mark, 1383.20 avg
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="ASML Holding N.V.",
            symbol="ASML",
            position=3.0,
            average_price=1383.20,
            mark_price=1425.91,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 2. QQQM: 96.39 pos, 270.75 mark, 263.754 avg
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="Invesco NASDAQ 100 ETF",
            symbol="QQQM",
            position=96.39,
            average_price=263.754,
            mark_price=270.75,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 3. SPYM: 307.92 pos, 86.70 mark, 83.446 avg
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="State Street SPDR Portfolio S&P 500 ETF",
            symbol="SPYM",
            position=307.92,
            average_price=83.446,
            mark_price=86.70,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 4. TSM: 18 pos, 377.50 mark, 328.448 avg
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="Taiwan Semiconductor Manufacturing Co.",
            symbol="TSM",
            position=18.0,
            average_price=328.448,
            mark_price=377.50,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # 5. HK0000923844: Money market fund (no units/prices, market_value 54565.17)
        Position(
            account_id="1001279250287283",
            broker_id="futubull-hk",
            instrument="ChinaAMC Select USD Money Market Fund",
            symbol="HK0000923844",
            position=None,
            average_price=None,
            mark_price=None,
            market_value=54565.17,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Account 1001272756530281 -> Futubull-HK (0281)
        # 6. BTC: 0.0791 pos, 75851.50 mark, 71472.82 avg
        Position(
            account_id="1001272756530281",
            broker_id="futubull-hk",
            instrument="Bitcoin",
            symbol="BTC",
            position=0.0791,
            average_price=71472.82,
            mark_price=75851.50,
            currency="USD",
            expiry_date=None,
            delivery_date=None,
            multiplier=1.0,
        ),
        # Account 1001281798927612 -> Futubull-HK (7612): No positions
    ],
}
