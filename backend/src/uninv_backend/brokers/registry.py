"""Which broker connectors are active.

This is the single place to switch a broker from simulated to real, e.g.
replace `mock_ibkr()` with `IbkrConnector(...)` once that exists.
"""

from uninv_backend.brokers.base import BrokerConnector
from uninv_backend.brokers.mock import mock_futu, mock_ibkr, mock_schwab


def get_connectors() -> list[BrokerConnector]:
    return [
        mock_ibkr(),
        mock_futu(),
        mock_schwab(),
    ]
