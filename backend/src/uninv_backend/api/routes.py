"""HTTP endpoints under /api/v1.

The desktop app talks to these through a generic Rust proxy, so a new endpoint added here
can be called from the UI right away. You don't need to touch any Rust.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from uninv_backend.brokers.registry import get_connectors
from uninv_backend.config import get_settings
from uninv_backend.fx import StaticFxProvider
from uninv_backend.models import (
    Account,
    Broker,
    PortfolioSummary,
    PositionGroup,
    PositionView,
)
from uninv_backend.portfolio.groups import get_groups
from uninv_backend.portfolio.service import PortfolioService

router = APIRouter(prefix="/api/v1")


@lru_cache
def get_portfolio_service() -> PortfolioService:
    """Dependency: a single shared service. Tests override this via `dependency_overrides`."""
    return PortfolioService(
        connectors=get_connectors(),
        groups=get_groups(),
        fx=StaticFxProvider(),
        base_currency=get_settings().base_currency,
    )


Service = Annotated[PortfolioService, Depends(get_portfolio_service)]


@router.get("/portfolio", response_model=PortfolioSummary, summary="Unified portfolio view")
async def portfolio(service: Service) -> PortfolioSummary:
    """Everything the dashboard needs in one call: totals, accounts, allocations, positions."""
    return await service.summary()


@router.get("/brokers", response_model=list[Broker])
async def brokers(service: Service) -> list[Broker]:
    return await service.brokers()


@router.get("/accounts", response_model=list[Account])
async def accounts(service: Service) -> list[Account]:
    return await service.accounts()


@router.get("/groups", response_model=list[PositionGroup])
async def groups(service: Service) -> list[PositionGroup]:
    return service.groups


@router.get("/positions", response_model=list[PositionView])
async def positions(
    service: Service,
    account_id: Annotated[str | None, Query(description="Only this account.")] = None,
    group_id: Annotated[str | None, Query(description="Only positions in this group.")] = None,
) -> list[PositionView]:
    summary = await service.summary()
    result = summary.positions
    if account_id is not None:
        if account_id not in {a.account.id for a in summary.accounts}:
            raise HTTPException(status_code=404, detail=f"Unknown account '{account_id}'")
        result = [p for p in result if p.account_id == account_id]
    if group_id is not None:
        if group_id not in {g.id for g in service.groups}:
            raise HTTPException(status_code=404, detail=f"Unknown group '{group_id}'")
        result = [p for p in result if group_id in p.group_ids]
    return result
