"""Graph-based foreign exchange (FX) routing and pathfinding.

Resolves exchange rates between any supported currency pair by finding the shortest
conversion path through directly-traded Forex markets on IBKR (IDEALPRO) or intermediate
currency hubs (e.g. USD, EUR, GBP).
"""

import logging
import math
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime

from uninv_backend.models import Currency

logger = logging.getLogger(__name__)

# Standard directly-traded Forex pairs on IBKR (IDEALPRO)
# In Forex market convention:
# EUR/USD, GBP/USD, AUD/USD, NZD/USD -> Base is foreign, Quote is USD
# USD/JPY, USD/CAD, USD/CHF, USD/HKD, USD/CNH, USD/SGD -> Base is USD, Quote is foreign
# Major cross pairs with direct liquidity:
# EUR/GBP, EUR/JPY, EUR/CHF, EUR/CAD, EUR/AUD
# GBP/JPY, GBP/CHF, GBP/AUD, GBP/CAD
# AUD/JPY, AUD/CAD, AUD/NZD
# CAD/JPY, CHF/JPY
DEFAULT_TRADED_PAIRS: list[tuple[Currency, Currency]] = [
    # Global Hub: USD
    (Currency.EUR, Currency.USD),
    (Currency.GBP, Currency.USD),
    (Currency.AUD, Currency.USD),
    (Currency.NZD, Currency.USD),
    (Currency.USD, Currency.JPY),
    (Currency.USD, Currency.CAD),
    (Currency.USD, Currency.CHF),
    (Currency.USD, Currency.HKD),
    (Currency.USD, Currency.CNH),
    (Currency.USD, Currency.SGD),
    # Regional Hub: EUR
    (Currency.EUR, Currency.GBP),
    (Currency.EUR, Currency.JPY),
    (Currency.EUR, Currency.CHF),
    (Currency.EUR, Currency.CAD),
    (Currency.EUR, Currency.AUD),
    # Regional Hub: GBP
    (Currency.GBP, Currency.JPY),
    (Currency.GBP, Currency.CHF),
    (Currency.GBP, Currency.AUD),
    (Currency.GBP, Currency.CAD),
    # Liquid Crosses
    (Currency.AUD, Currency.JPY),
    (Currency.AUD, Currency.CAD),
    (Currency.AUD, Currency.NZD),
    (Currency.CAD, Currency.JPY),
    (Currency.CHF, Currency.JPY),
]


class FxRouter:
    """Graph-based router for foreign exchange conversions."""

    def __init__(
        self,
        known_pairs: list[tuple[Currency, Currency]] | None = None,
        cache_ttl_seconds: float = 15.0,
    ) -> None:
        self.cache_ttl = cache_ttl_seconds
        # In-memory edge cache: (u, v) -> (rate, timestamp)
        self._cache: dict[tuple[Currency, Currency], tuple[float, float]] = {}
        # Undirected graph adjacency representation
        self._adj: dict[Currency, set[Currency]] = {c: set() for c in Currency}
        pairs = known_pairs if known_pairs is not None else DEFAULT_TRADED_PAIRS
        for u, v in pairs:
            self.add_market_pair(u, v)

    def add_market_pair(self, u: Currency, v: Currency) -> None:
        """Register a known directly-tradeable market pair in the graph."""
        if u not in self._adj:
            self._adj[u] = set()
        if v not in self._adj:
            self._adj[v] = set()
        self._adj[u].add(v)
        self._adj[v].add(u)

    def find_path(
        self,
        start: Currency,
        target: Currency,
        blocked_edges: set[tuple[Currency, Currency]] | None = None,
    ) -> list[Currency] | None:
        """Find the shortest currency path from start to target using BFS.

        Excludes any edges specified in `blocked_edges`.
        """
        if start == target:
            return [start]

        blocked = blocked_edges or set()

        # Check direct 1-hop path first
        if target in self._adj.get(start, set()) and (start, target) not in blocked:
            return [start, target]

        queue: deque[list[Currency]] = deque([[start]])
        visited: set[Currency] = {start}

        while queue:
            current_path = queue.popleft()
            node = current_path[-1]

            neighbors = sorted(
                self._adj.get(node, set()),
                # Prioritize USD and EUR hubs for faster routing
                key=lambda c: 0 if c == Currency.USD else (1 if c == Currency.EUR else 2),
            )

            for nxt in neighbors:
                if (node, nxt) in blocked or (nxt, node) in blocked:
                    continue
                if nxt == target:
                    return [*current_path, nxt]
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append([*current_path, nxt])

        # Fallback: if not connected in graph, try route through USD hub
        if (
            start != Currency.USD
            and target != Currency.USD
            and (start, Currency.USD) not in blocked
            and (Currency.USD, target) not in blocked
        ):
            return [start, Currency.USD, target]

        return None

    def get_rate(
        self,
        base: Currency,
        quote: Currency,
        probe_fn: Callable[[str], float | None],
        asof: datetime | None = None,
    ) -> tuple[float, datetime]:
        """Resolve exchange rate from base to quote using graph routing.

        1 unit of base = rate units of quote.
        """
        query_asof = asof or datetime.now(UTC)
        if base == quote:
            return 1.0, query_asof

        now = time.time()
        cache_key = (base, quote)
        if cache_key in self._cache:
            rate, ts = self._cache[cache_key]
            if now - ts < self.cache_ttl:
                return rate, query_asof

        blocked_edges: set[tuple[Currency, Currency]] = set()

        while True:
            path = self.find_path(base, quote, blocked_edges)
            if not path or len(path) < 2:
                raise ValueError(
                    f"Could not resolve exchange rate for {base.value}/{quote.value} (no path)"
                )

            path_success = True
            hop_rates: list[float] = []

            for i in range(len(path) - 1):
                u = path[i]
                v = path[i + 1]

                # Check edge cache
                edge_key = (u, v)
                if edge_key in self._cache and (now - self._cache[edge_key][1] < self.cache_ttl):
                    hop_rates.append(self._cache[edge_key][0])
                    continue

                # 1. Try direct pair (e.g. 'EURUSD')
                direct_symbol = f"{u.value}{v.value}"
                direct_rate = probe_fn(direct_symbol)
                if direct_rate is not None and not math.isnan(direct_rate) and direct_rate > 0:
                    self._cache[(u, v)] = (direct_rate, now)
                    self._cache[(v, u)] = (1.0 / direct_rate, now)
                    self.add_market_pair(u, v)
                    hop_rates.append(direct_rate)
                    continue

                # 2. Try inverted pair (e.g. 1.0 / 'USDEUR')
                inverted_symbol = f"{v.value}{u.value}"
                inv_rate = probe_fn(inverted_symbol)
                if inv_rate is not None and not math.isnan(inv_rate) and inv_rate > 0:
                    rate = 1.0 / inv_rate
                    self._cache[(u, v)] = (rate, now)
                    self._cache[(v, u)] = (inv_rate, now)
                    self.add_market_pair(u, v)
                    hop_rates.append(rate)
                    continue

                # Neither direct nor inverted quote succeeded on this edge
                logger.debug(
                    "FX probe failed on %s -> %s; blocking edge and searching alternative path",
                    u.value,
                    v.value,
                )
                blocked_edges.add((u, v))
                blocked_edges.add((v, u))
                path_success = False
                break

            if path_success:
                total_rate = math.prod(hop_rates)
                self._cache[(base, quote)] = (total_rate, now)
                self._cache[(quote, base)] = (1.0 / total_rate, now)
                return total_rate, query_asof
