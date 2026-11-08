"""HTTP endpoints under /api/v1."""

import logging
from typing import Annotated

import anyio
from fastapi import APIRouter, HTTPException, Query

from uninv_backend.config import update_broker_gateway
from uninv_backend.futu import futu_service
from uninv_backend.ibkr import ibkr_service
from uninv_backend.models import (
    AccountsResponse,
    BrokerAccountSnapshot,
    BrokerConnectionTestResponse,
    BrokerGatewayConfig,
    BrokerGatewayConfigRequest,
    BrokerGatewayConfigResponse,
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
            description="Broker account ID, e.g. 'U1234567' or '88888888'",
            examples=["U1234567", "88888888"],
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


@router.get(
    "/broker-connection-test",
    response_model=BrokerConnectionTestResponse,
    summary="Test connectivity to a broker gateway daemon",
)
async def test_broker_connection(
    broker_id: Annotated[
        str,
        Query(
            description="Broker identifier, e.g. 'ibkr' or 'futu'",
            examples=["ibkr", "futu"],
        ),
    ],
) -> BrokerConnectionTestResponse:
    """Test if broker gateway daemon is actively reachable."""
    if broker_id == "ibkr":
        connected, message = await ibkr_service.test_connection()
        return BrokerConnectionTestResponse(
            broker_id=broker_id, connected=connected, message=message
        )
    elif broker_id == "futu":
        connected, message = await anyio.to_thread.run_sync(futu_service.test_connection)
        return BrokerConnectionTestResponse(
            broker_id=broker_id, connected=connected, message=message
        )
    else:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")


@router.get(
    "/broker-gateway-config",
    response_model=BrokerGatewayConfigResponse,
    summary="Get current configured host and ports for broker gateways",
)
def get_broker_gateway_config() -> BrokerGatewayConfigResponse:
    """Return currently configured host and TCP ports for all supported broker gateways."""
    gateways = {
        "ibkr": BrokerGatewayConfig(host=ibkr_service.host, port=ibkr_service.port),
        "futu": BrokerGatewayConfig(host=futu_service.host, port=futu_service.port),
    }
    return BrokerGatewayConfigResponse(
        status="ok",
        gateways=gateways,
    )


@router.post(
    "/broker-gateway-config",
    response_model=BrokerGatewayConfigResponse,
    summary="Update broker gateway host and port configuration",
)
def update_broker_gateway_config(
    payload: BrokerGatewayConfigRequest,
) -> BrokerGatewayConfigResponse:
    """Update gateway host and/or port for a broker and re-initialize connection pool."""
    broker_id = payload.broker_id.lower().strip()
    host = payload.host
    port = payload.port

    if broker_id == "ibkr":
        ibkr_service.set_gateway(host=host, port=port)
        update_broker_gateway("ibkr", host=host, port=port)
    elif broker_id == "futu":
        futu_service.set_gateway(host=host, port=port)
        update_broker_gateway("futu", host=host, port=port)
    else:
        raise HTTPException(status_code=404, detail=f"Broker '{broker_id}' not supported")

    return get_broker_gateway_config()
