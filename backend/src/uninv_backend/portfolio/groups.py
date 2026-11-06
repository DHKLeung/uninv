"""User-defined position groups.

Hardcoded for now. Later they should be stored locally (e.g. SQLite) and edited from the
desktop app. Groups reference positions by `Position.id` ("<account_id>:<symbol>"), so a
group can span accounts and brokers, and one position can be in several groups.
Ids that don't match a current position are ignored, e.g. after a position is closed.
"""

from uninv_backend.models import PositionGroup


def get_groups() -> list[PositionGroup]:
    return [
        PositionGroup(
            id="core",
            name="Core Index",
            description="Broad-market index ETFs: the long-term core.",
            color="#4f8cff",
            position_ids=[
                "ibkr-U1234567:VOO",
                "schwab-IRA-4821:VTI",
                "futu-HK001:2800.HK",
            ],
        ),
        PositionGroup(
            id="big-tech",
            name="Big Tech",
            description="Large-cap technology across US and HK.",
            color="#a970ff",
            position_ids=[
                "ibkr-U1234567:AAPL",
                "ibkr-U1234567:MSFT",
                "ibkr-U1234567:NVDA",
                "ibkr-U1234567:AAPL270115C00250000",
                "schwab-BRK-9917:GOOGL",
                "schwab-BRK-9917:AMZN",
                "schwab-BRK-9917:MSFT",
                "futu-HK001:0700.HK",
                "futu-HK001:9988.HK",
            ],
        ),
        PositionGroup(
            id="income",
            name="Income & Bonds",
            description="Dividend and fixed-income holdings.",
            color="#2fbf71",
            position_ids=[
                "schwab-IRA-4821:SCHD",
                "schwab-IRA-4821:BND",
                "ibkr-U1234567:TLT",
            ],
        ),
        PositionGroup(
            id="hong-kong",
            name="Hong Kong",
            description="HK-listed exposure.",
            color="#ff8a3d",
            position_ids=[
                "futu-HK001:0700.HK",
                "futu-HK001:2800.HK",
                "futu-HK001:9988.HK",
            ],
        ),
        PositionGroup(
            id="speculative",
            name="Speculative",
            description="Options and high-volatility names.",
            color="#ff5470",
            position_ids=[
                "ibkr-U1234567:AAPL270115C00250000",
                "futu-HK001:TSLA",
            ],
        ),
    ]
