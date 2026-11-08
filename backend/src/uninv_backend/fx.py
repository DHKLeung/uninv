"""Foreign exchange (FX) matrix router and rate calculation service.

Constructs a complete (N x N) cross currency matrix across all supported currencies
by fetching live quotes for directly-traded Forex market pairs on IBKR (IDEALPRO)
against the global USD hub, with automatic inversion, cross-rate synthesis,
in-memory caching, and robust fallbacks.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from uninv_backend.models import Currency, FxMatrixResponse

logger = logging.getLogger(__name__)

# Standard directly-traded Forex pairs on IBKR (IDEALPRO):
# Foreign/USD direct pairs: Base is Foreign, Quote is USD (1 Foreign = X USD)
DIRECT_FOREIGN_USD_PAIRS: dict[Currency, str] = {
    Currency.EUR: "EURUSD",
    Currency.GBP: "GBPUSD",
    Currency.AUD: "AUDUSD",
    Currency.NZD: "NZDUSD",
}

# USD/Foreign direct pairs: Base is USD, Quote is Foreign (1 USD = X Foreign)
USD_FOREIGN_PAIRS: dict[Currency, str] = {
    Currency.JPY: "USDJPY",
    Currency.CAD: "USDCAD",
    Currency.CHF: "USDCHF",
    Currency.HKD: "USDHKD",
    Currency.CNH: "USDCNH",
    Currency.SGD: "USDSGD",
}

ALL_IDEALPRO_PAIRS: list[str] = list(DIRECT_FOREIGN_USD_PAIRS.values()) + list(
    USD_FOREIGN_PAIRS.values()
)

# Reference fallback rates (1 unit of currency = X USD) if socket feed is unavailable
DEFAULT_USD_RATES: dict[Currency, float] = {
    Currency.USD: 1.0,
    Currency.EUR: 1.0850,
    Currency.GBP: 1.2950,
    Currency.AUD: 0.6550,
    Currency.NZD: 0.5950,
    Currency.JPY: 1.0 / 154.20,
    Currency.CAD: 1.0 / 1.3920,
    Currency.CHF: 1.0 / 0.8820,
    Currency.HKD: 1.0 / 7.7810,
    Currency.CNH: 1.0 / 7.2350,
    Currency.SGD: 1.0 / 1.3320,
}


class FxRouter:
    """Calculates and serves the complete FX exchange rate matrix across all currencies."""

    def __init__(self, cache_ttl_seconds: float = 60.0) -> None:
        self.cache_ttl = cache_ttl_seconds
        # In-memory edge cache: (u, v) -> (rate, timestamp)
        self._cache: dict[tuple[Currency, Currency], tuple[float, float]] = {}
        self._cached_matrix: tuple[dict[Currency, dict[Currency, float]], float] | None = None

    def _synthesize_matrix(
        self,
        quotes: dict[str, float],
        query_asof: datetime,
        now: float,
        currencies: list[Currency],
    ) -> FxMatrixResponse:
        """Synthesize reciprocal and cross-currency rates matrix from probed quotes."""
        usd_val: dict[Currency, float] = {Currency.USD: 1.0}

        # Foreign/USD pairs (EUR, GBP, AUD, NZD)
        for foreign_ccy, pair in DIRECT_FOREIGN_USD_PAIRS.items():
            rate = quotes.get(pair)
            if rate is not None and rate > 0:
                usd_val[foreign_ccy] = rate
            else:
                usd_val[foreign_ccy] = DEFAULT_USD_RATES[foreign_ccy]

        # USD/Foreign pairs (JPY, CAD, CHF, HKD, CNH, SGD)
        for foreign_ccy, pair in USD_FOREIGN_PAIRS.items():
            rate = quotes.get(pair)
            if rate is not None and rate > 0:
                usd_val[foreign_ccy] = 1.0 / rate
            else:
                usd_val[foreign_ccy] = DEFAULT_USD_RATES[foreign_ccy]

        rates: dict[Currency, dict[Currency, float]] = {}
        for u in currencies:
            rates[u] = {}
            for v in currencies:
                if u == v:
                    rates[u][v] = 1.0
                else:
                    rate_uv = usd_val[u] / usd_val[v]
                    rates[u][v] = rate_uv
                    self._cache[(u, v)] = (rate_uv, now)

        self._cached_matrix = (rates, now)
        return FxMatrixResponse(asof=query_asof, currencies=currencies, rates=rates)

    async def get_matrix_async(
        self,
        batch_probe_fn: Callable[[list[str]], Awaitable[dict[str, float]]],
        asof: datetime | None = None,
    ) -> FxMatrixResponse:
        """Asynchronously construct the complete (N x N) currency conversion matrix."""
        query_asof = asof or datetime.now(UTC)
        now = time.time()
        currencies = list(Currency)

        if self._cached_matrix is not None:
            cached_rates, cached_ts = self._cached_matrix
            if now - cached_ts < self.cache_ttl:
                return FxMatrixResponse(asof=query_asof, currencies=currencies, rates=cached_rates)

        quotes: dict[str, float] = {}
        try:
            quotes = await batch_probe_fn(ALL_IDEALPRO_PAIRS) or {}
        except Exception as e:
            logger.debug("FX async batch quote probe error: %s", e)

        return self._synthesize_matrix(quotes, query_asof, now, currencies)

    def get_matrix(
        self,
        batch_probe_fn: Callable[[list[str]], dict[str, float]],
        asof: datetime | None = None,
    ) -> FxMatrixResponse:
        """Construct the complete (N x N) currency conversion matrix.

        Queries live market quotes for tradeable IDEALPRO pairs in a single batched call,
        then synthesizes all reciprocal and cross-currency rates.
        """
        query_asof = asof or datetime.now(UTC)
        now = time.time()
        currencies = list(Currency)

        # Check in-memory matrix cache
        if self._cached_matrix is not None:
            cached_rates, cached_ts = self._cached_matrix
            if now - cached_ts < self.cache_ttl:
                return FxMatrixResponse(asof=query_asof, currencies=currencies, rates=cached_rates)

        # 1. Fetch live quotes for all tradeable Forex pairs in a single batched call
        quotes: dict[str, float] = {}
        try:
            quotes = batch_probe_fn(ALL_IDEALPRO_PAIRS) or {}
        except Exception as e:
            logger.debug("FX batch quote probe error: %s", e)

        return self._synthesize_matrix(quotes, query_asof, now, currencies)

    def get_rate(
        self,
        base: Currency,
        quote: Currency,
        batch_probe_fn: Callable[[list[str]], dict[str, float]],
        asof: datetime | None = None,
    ) -> tuple[float, datetime]:
        """Return conversion rate from base to quote."""
        matrix = self.get_matrix(batch_probe_fn, asof=asof)
        return matrix.rates[base][quote], matrix.asof
