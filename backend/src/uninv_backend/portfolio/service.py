"""Builds the unified portfolio from all connected brokers."""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from uninv_backend.brokers.base import BrokerConnector
from uninv_backend.fx import FxProvider
from uninv_backend.models import (
    Account,
    AccountSummary,
    AllocationSlice,
    AssetClass,
    Broker,
    BrokerError,
    PortfolioSummary,
    PortfolioTotals,
    Position,
    PositionGroup,
    PositionView,
)

logger = logging.getLogger(__name__)

ASSET_CLASS_LABELS: dict[str, str] = {
    AssetClass.STOCK: "Stocks",
    AssetClass.ETF: "ETFs",
    AssetClass.OPTION: "Options",
    AssetClass.BOND: "Bonds",
    AssetClass.FUND: "Funds",
    AssetClass.CRYPTO: "Crypto",
    AssetClass.CASH: "Cash",
}


@dataclass
class _RawData:
    """Everything fetched from the brokers in one refresh."""

    brokers: list[Broker] = field(default_factory=list)
    accounts: list[Account] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    errors: list[BrokerError] = field(default_factory=list)


class PortfolioService:
    def __init__(
        self,
        connectors: list[BrokerConnector],
        groups: list[PositionGroup],
        fx: FxProvider,
        base_currency: str = "USD",
    ) -> None:
        self._connectors = connectors
        self._groups = groups
        self._fx = fx
        self.base_currency = base_currency

    # ----------------------------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------------------------

    @property
    def groups(self) -> list[PositionGroup]:
        return list(self._groups)

    async def brokers(self) -> list[Broker]:
        return [c.info for c in self._connectors]

    async def accounts(self) -> list[Account]:
        return (await self._fetch()).accounts

    async def summary(self) -> PortfolioSummary:
        return self._build_summary(await self._fetch())

    # ----------------------------------------------------------------------------------
    # Fetching
    # ----------------------------------------------------------------------------------

    async def _fetch(self) -> _RawData:
        """Query every broker concurrently. A failing broker is reported, not fatal."""
        results = await asyncio.gather(
            *(self._fetch_one(c) for c in self._connectors), return_exceptions=True
        )
        data = _RawData()
        for connector, result in zip(self._connectors, results, strict=True):
            data.brokers.append(connector.info)
            if isinstance(result, BaseException):
                logger.exception("Broker %s failed", connector.info.id, exc_info=result)
                data.errors.append(BrokerError(broker_id=connector.info.id, message=str(result)))
                continue
            accounts, positions = result
            data.accounts.extend(accounts)
            data.positions.extend(positions)
        return data

    @staticmethod
    async def _fetch_one(connector: BrokerConnector) -> tuple[list[Account], list[Position]]:
        accounts, positions = await asyncio.gather(
            connector.get_accounts(), connector.get_positions()
        )
        return accounts, positions

    # ----------------------------------------------------------------------------------
    # Aggregation
    # ----------------------------------------------------------------------------------

    def _build_summary(self, data: _RawData) -> PortfolioSummary:
        base = self.base_currency
        broker_names = {b.id: b.name for b in data.brokers}

        # Which groups each position belongs to.
        groups_by_position: dict[str, list[str]] = defaultdict(list)
        for group in self._groups:
            for pid in group.position_ids:
                groups_by_position[pid].append(group.id)

        # Cash per account, converted to base currency.
        cash_base = {a.id: a.cash_balance * self._fx.rate(a.currency, base) for a in data.accounts}

        # First pass: convert positions to base currency (weights need the grand total).
        converted: list[tuple[Position, float]] = [
            (p, self._fx.rate(p.currency, base)) for p in data.positions
        ]
        positions_value = sum(p.market_value * r for p, r in converted)
        cost_basis = sum(p.cost_basis * r for p, r in converted)
        cash_total = sum(cash_base.values())
        net_liq = positions_value + cash_total

        def weight(value: float) -> float:
            return value / net_liq if net_liq else 0.0

        views = [
            PositionView(
                **p.model_dump(exclude={"id", "market_value", "cost_basis", "unrealized_pnl"}),
                fx_rate=rate,
                market_value_base=p.market_value * rate,
                cost_basis_base=p.cost_basis * rate,
                unrealized_pnl_base=p.unrealized_pnl * rate,
                unrealized_pnl_pct=(p.unrealized_pnl / abs(p.cost_basis)) if p.cost_basis else 0.0,
                weight=weight(p.market_value * rate),
                group_ids=groups_by_position.get(p.id, []),
            )
            for p, rate in converted
        ]
        views.sort(key=lambda v: v.market_value_base, reverse=True)

        unrealized = positions_value - cost_basis
        totals = PortfolioTotals(
            positions_value=positions_value,
            cash=cash_total,
            net_liquidation=net_liq,
            cost_basis=cost_basis,
            unrealized_pnl=unrealized,
            unrealized_pnl_pct=(unrealized / abs(cost_basis)) if cost_basis else 0.0,
        )

        # Per account.
        accounts: list[AccountSummary] = []
        for acct in data.accounts:
            acct_views = [v for v in views if v.account_id == acct.id]
            pv = sum(v.market_value_base for v in acct_views)
            nl = pv + cash_base[acct.id]
            accounts.append(
                AccountSummary(
                    account=acct,
                    broker_name=broker_names.get(acct.broker_id, acct.broker_id),
                    positions_value=pv,
                    cash=cash_base[acct.id],
                    net_liquidation=nl,
                    unrealized_pnl=sum(v.unrealized_pnl_base for v in acct_views),
                    weight=weight(nl),
                    position_count=len(acct_views),
                )
            )
        accounts.sort(key=lambda a: a.net_liquidation, reverse=True)

        # Allocation breakdowns. Cash is included in asset-class and currency views so
        # those slices add up to 100% of net liquidation.
        by_asset_class = _slices(
            views,
            key=lambda v: v.asset_class.value,
            label=lambda v: ASSET_CLASS_LABELS.get(v.asset_class, v.asset_class.value),
            weight=weight,
        )
        if cash_total:
            by_asset_class.append(
                AllocationSlice(
                    key=AssetClass.CASH.value,
                    label=ASSET_CLASS_LABELS[AssetClass.CASH],
                    market_value=cash_total,
                    unrealized_pnl=0.0,
                    weight=weight(cash_total),
                    position_count=0,
                )
            )
        by_asset_class.sort(key=lambda s: s.market_value, reverse=True)

        by_currency = _slices(
            views, key=lambda v: v.currency, label=lambda v: v.currency, weight=weight
        )
        by_currency = _add_cash_by_currency(by_currency, data.accounts, cash_base, weight)

        by_symbol = _slices(views, key=lambda v: v.symbol, label=lambda v: v.name, weight=weight)

        groups: list[AllocationSlice] = []
        for group in self._groups:
            members = [v for v in views if group.id in v.group_ids]
            mv = sum(v.market_value_base for v in members)
            groups.append(
                AllocationSlice(
                    key=group.id,
                    label=group.name,
                    market_value=mv,
                    unrealized_pnl=sum(v.unrealized_pnl_base for v in members),
                    weight=weight(mv),
                    position_count=len(members),
                    color=group.color,
                )
            )

        return PortfolioSummary(
            base_currency=base,
            as_of=datetime.now(UTC),
            totals=totals,
            brokers=data.brokers,
            accounts=accounts,
            by_asset_class=by_asset_class,
            by_currency=by_currency,
            by_symbol=by_symbol,
            groups=groups,
            positions=views,
            errors=data.errors,
        )


def _slices(
    views: Iterable[PositionView],
    key: Callable[[PositionView], str],
    label: Callable[[PositionView], str],
    weight: Callable[[float], float],
) -> list[AllocationSlice]:
    """Group positions by `key` and sum their base-currency values."""
    buckets: dict[str, list[PositionView]] = defaultdict(list)
    for v in views:
        buckets[key(v)].append(v)
    slices = []
    for k, members in buckets.items():
        mv = sum(m.market_value_base for m in members)
        slices.append(
            AllocationSlice(
                key=k,
                label=label(members[0]),
                market_value=mv,
                unrealized_pnl=sum(m.unrealized_pnl_base for m in members),
                weight=weight(mv),
                position_count=len(members),
            )
        )
    slices.sort(key=lambda s: s.market_value, reverse=True)
    return slices


def _add_cash_by_currency(
    slices: list[AllocationSlice],
    accounts: list[Account],
    cash_base: dict[str, float],
    weight: Callable[[float], float],
) -> list[AllocationSlice]:
    by_key = {s.key: s for s in slices}
    for acct in accounts:
        cash = cash_base[acct.id]
        if not cash:
            continue
        s = by_key.get(acct.currency)
        if s is None:
            s = AllocationSlice(
                key=acct.currency,
                label=acct.currency,
                market_value=0.0,
                unrealized_pnl=0.0,
                weight=0.0,
                position_count=0,
            )
            by_key[acct.currency] = s
        s.market_value += cash
        s.weight = weight(s.market_value)
    return sorted(by_key.values(), key=lambda s: s.market_value, reverse=True)
