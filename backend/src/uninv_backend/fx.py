"""Currency conversion.

Uses hardcoded rates for now. Swap `StaticFxProvider` for a live implementation later;
anything with a `rate(from_ccy, to_ccy)` method will work.
"""

from typing import Protocol

# Approximate rates, *for simulation only*: 1 unit of currency = N USD.
_STATIC_RATES_TO_USD: dict[str, float] = {
    "USD": 1.0,
    "HKD": 0.1285,
    "EUR": 1.08,
    "GBP": 1.27,
    "JPY": 0.0066,
    "CNY": 0.138,
    "SGD": 0.74,
}


class FxProvider(Protocol):
    def rate(self, from_ccy: str, to_ccy: str) -> float:
        """Return how many `to_ccy` one unit of `from_ccy` buys."""
        ...


class StaticFxProvider:
    def __init__(self, rates_to_usd: dict[str, float] | None = None) -> None:
        self._rates = rates_to_usd or _STATIC_RATES_TO_USD

    def rate(self, from_ccy: str, to_ccy: str) -> float:
        if from_ccy == to_ccy:
            return 1.0
        try:
            return self._rates[from_ccy] / self._rates[to_ccy]
        except KeyError as exc:
            raise ValueError(f"No FX rate for {exc.args[0]}") from exc
