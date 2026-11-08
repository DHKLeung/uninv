"""HTTP endpoints under /api/v1."""

import logging
from typing import Annotated

import anyio
from fastapi import APIRouter, HTTPException, Query

from uninv_backend.futu import futu_service
from uninv_backend.ibkr import ibkr_service
from uninv_backend.models import (
    AccountsResponse,
    BrokerAccountSnapshot,
    FxMatrixResponse,
    SupportingBroker,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

SUPPORTING_BROKERS = [
    SupportingBroker(id="ibkr", name="Interactive Brokers"),
    SupportingBroker(id="futu", name="Futu"),
]


@router.get(
    "/supporting-brokers",
    response_model=list[SupportingBroker],
    summary="List supported brokers",
)
def get_supporting_brokers() -> list[SupportingBroker]:
    """Return the list of brokers supported by this backend."""
    return SUPPORTING_BROKERS


@router.get(
    "/accounts",
    response_model=AccountsResponse,
    summary="List accounts for a broker",
)
async def get_accounts(
    broker_id: Annotated[
        str,
        Query(
            description="Broker identifier, e.g. 'ibkr' or 'futu'",
            examples=["ibkr", "futu"],
        ),
    ],
) -> AccountsResponse:
    """Return managed accounts with query timestamp."""
    if broker_id == "ibkr":
        try:
            accounts, asof = await ibkr_service.get_accounts()
            return AccountsResponse(broker_id=broker_id, asof=asof, accounts=accounts)
        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            logger.exception("Error fetching IBKR accounts")
            raise HTTPException(status_code=500, detail=str(e)) from e
    elif broker_id == "futu":
        try:
            accounts, asof = await anyio.to_thread.run_sync(futu_service.get_accounts)
            return AccountsResponse(broker_id=broker_id, asof=asof, accounts=accounts)
        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except Exception as e:
            logger.exception("Error fetching Futu accounts")
            raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")


@router.get(
    "/snapshot",
    response_model=BrokerAccountSnapshot,
    summary="Get unified broker account snapshot",
)
async def get_snapshot(
    broker_id: Annotated[
        str,
        Query(
            description="Broker identifier, e.g. 'ibkr' or 'futu'",
            examples=["ibkr", "futu"],
        ),
    ],
    account_id: Annotated[
        str,
        Query(
            description="Broker account ID, e.g. 'U16110728' or '28173918'",
            examples=["U16110728", "28173918"],
        ),
    ],
) -> BrokerAccountSnapshot:
    """Return complete account snapshot including margins, cash balances, and positions."""
    if broker_id == "ibkr":
        try:
            return await ibkr_service.get_snapshot(account_id)
        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            logger.exception(f"Error fetching IBKR snapshot for {account_id}")
            raise HTTPException(status_code=500, detail=str(e)) from e
    elif broker_id == "futu":
        try:
            return await anyio.to_thread.run_sync(futu_service.get_snapshot, account_id)
        except ConnectionError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except Exception as e:
            logger.exception(f"Error fetching Futu snapshot for {account_id}")
            raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")


@router.get(
    "/fx",
    response_model=FxMatrixResponse,
    summary="Get complete foreign exchange matrix across all currencies",
)
async def get_fx() -> FxMatrixResponse:
    """Return complete exchange rate matrix between all supported currencies with UTC timestamp."""
    try:
        return await ibkr_service.get_fx_matrix()
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error constructing FX matrix")
        raise HTTPException(status_code=500, detail=str(e)) from e
