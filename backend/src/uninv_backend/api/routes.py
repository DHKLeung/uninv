"""HTTP endpoints under /api/v1."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from uninv_backend.data import ACCOUNTS, BROKERS, CASH_BALANCES, POSITIONS
from uninv_backend.models import AccountMetadata, Broker, CashBalance, Position

router = APIRouter(prefix="/api/v1")


@router.get("/brokers", response_model=list[Broker], summary="List brokers")
async def get_brokers() -> list[Broker]:
    """Return the available brokers."""
    return BROKERS


@router.get(
    "/accounts/{broker_id}",
    response_model=list[AccountMetadata],
    summary="List accounts for a broker",
)
async def get_accounts(broker_id: str) -> list[AccountMetadata]:
    """Return account metadata for the specified broker (e.g. 'ibkr-hk', 'futubull-hk')."""
    if broker_id not in ACCOUNTS:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not found")
    return ACCOUNTS[broker_id]


@router.get(
    "/cash-balance/{broker_id}",
    response_model=CashBalance | list[CashBalance],
    summary="Get cash balance for an account or broker",
)
async def get_cash_balance(
    broker_id: str,
    account_id: Annotated[
        str | None, Query(description="Filter by specific broker account ID")
    ] = None,
) -> CashBalance | list[CashBalance]:
    """Return cash balance for the specified broker and account."""
    if broker_id not in CASH_BALANCES:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not found")

    balances = CASH_BALANCES[broker_id]
    if account_id is not None:
        for b in balances:
            if b.account_id == account_id:
                return b
        raise HTTPException(
            status_code=404,
            detail=f"Account '{account_id}' not found for broker '{broker_id}'",
        )
    return balances


@router.get(
    "/positions/{broker_id}",
    response_model=list[Position],
    summary="List positions for a broker",
)
async def get_positions(
    broker_id: str,
    account_id: Annotated[
        str | None, Query(description="Filter by specific broker account ID")
    ] = None,
) -> list[Position]:
    """Return positions for the specified broker, optionally filtered by account_id."""
    if broker_id not in POSITIONS:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not found")

    positions = POSITIONS[broker_id]
    if account_id is not None:
        valid_account_ids = {a.account_id for a in ACCOUNTS.get(broker_id, [])}
        if account_id not in valid_account_ids:
            raise HTTPException(
                status_code=404,
                detail=f"Account '{account_id}' not found for broker '{broker_id}'",
            )
        positions = [p for p in positions if p.account_id == account_id]

    return positions
