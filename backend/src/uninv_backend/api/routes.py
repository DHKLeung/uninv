"""HTTP endpoints under /api/v1."""

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from uninv_backend.ibkr import ibkr_service
from uninv_backend.models import (
    AccountsResponse,
    BrokerAccountSnapshot,
    Currency,
    FxRate,
    SupportingBroker,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

SUPPORTING_BROKERS = [
    SupportingBroker(id="ibkr", name="Interactive Brokers"),
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
def get_accounts(
    broker_id: Annotated[
        str,
        Query(
            description="Broker identifier, e.g. 'ibkr'",
            examples=["ibkr"],
        ),
    ],
) -> AccountsResponse:
    """Return managed accounts with query timestamp."""
    if broker_id != "ibkr":
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")

    try:
        accounts, asof = ibkr_service.get_accounts()
        return AccountsResponse(broker_id=broker_id, asof=asof, accounts=accounts)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except Exception as e:
        logger.exception("Error fetching IBKR accounts")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/snapshot",
    response_model=BrokerAccountSnapshot,
    summary="Get unified broker account snapshot",
)
def get_snapshot(
    broker_id: Annotated[
        str,
        Query(
            description="Broker identifier, e.g. 'ibkr'",
            examples=["ibkr"],
        ),
    ],
    account_id: Annotated[
        str,
        Query(
            description="Broker account ID, e.g. 'U16110728'",
            examples=["U16110728"],
        ),
    ],
) -> BrokerAccountSnapshot:
    """Return complete account snapshot including margins, cash balances, and positions."""
    if broker_id != "ibkr":
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")

    try:
        return ibkr_service.get_snapshot(account_id)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching snapshot for {account_id}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/fx",
    response_model=FxRate,
    summary="Get live foreign exchange rate",
)
def get_fx(
    base: Annotated[
        Currency,
        Query(
            description="Base currency code, e.g. 'EUR'",
            examples=["EUR"],
        ),
    ],
    quote: Annotated[
        Currency,
        Query(
            description="Quote currency code, e.g. 'USD'",
            examples=["USD"],
        ),
    ],
) -> FxRate:
    """Return current exchange rate where 1 unit of base = rate units of quote."""
    try:
        rate, asof = ibkr_service.get_fx_rate(base, quote)
        return FxRate(base=base, quote=quote, rate=float(rate), asof=asof)
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching FX rate for {base.value}/{quote.value}")
        raise HTTPException(status_code=500, detail=str(e)) from e
