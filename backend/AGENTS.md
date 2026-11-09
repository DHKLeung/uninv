# AGENTS.md: backend (Python / FastAPI)

Rules for `backend/`. Root `AGENTS.md` applies too.

## Layout
- `src/uninv_backend/models.py`: Pydantic models with strict `StrEnum`s (`Currency`, `Exchange`, `SecurityType`, `OptionType`). Defines `AccountsResponse`, `BrokerAccountSnapshot`, `AccountValues`, `Position`, `FxMatrixResponse`, `SupportingBroker`, `BrokerGatewayConfig`, `BrokerGatewayConfigRequest`, `BrokerGatewayConfigResponse`, `BrokerConnectionTestResponse`. Single source of truth for data shapes.
- `src/uninv_backend/ibkr.py`: Pure async IBKR connector service (`IBKRService`, `ibkr_service`) wrapping `ib_async` natively on the main asyncio event loop. Connects directly to TWS on port 7496 or IB Gateway on port 4001. Provides `get_snapshot`, `get_fx_matrix`, and auto-reconnection with strict network timeouts.
- `src/uninv_backend/futu.py`: Futu meta-broker connector service (`FutuService`, `futu_service`) wrapping `futu-api`. Connects to OpenD on port 11111 with fast TCP pre-flight socket probing, daemon thread configuration, multi-context traversal (Securities, Futures, Crypto), and zero-cache live snapshot queries.
- `src/uninv_backend/fx.py`: `FxRouter` service calculating and serving the complete 11×11 FX exchange rate matrix across all currencies with graph-based cross-rate synthesis.
- `src/uninv_backend/api/routes.py`: `/api/v1` routes:
  - `GET /api/v1/supporting-brokers`: returns `[{"id": "ibkr", ...}, {"id": "futu", ...}]`.
  - `GET /api/v1/accounts?broker_id={ibkr|futu}`: returns `AccountsResponse` with UTC `asof` timestamp.
  - `GET /api/v1/snapshot?broker_id={ibkr|futu}&account_id={id}`: returns `BrokerAccountSnapshot` with UTC `asof` timestamp.
  - `GET /api/v1/fx`: returns `FxMatrixResponse` with full 11x11 rates matrix, currencies list, and UTC `asof` timestamp.
  - `GET /api/v1/broker-connection-test?broker_id={ibkr|futu}`: tests broker gateway TCP connection and handshake.
  - `GET /api/v1/broker-gateway-config`: returns current configured host and ports for broker gateways.
  - `POST /api/v1/broker-gateway-config`: updates configured host and/or port for a broker gateway.
- `config.py`: `Settings` (env prefix `UNINV_`), `update_broker_gateway(broker_id, host, port)`.
- `app.py`: FastAPI app initialization, CORS setup, and `/health`.

## Conventions
- Python 3.13, full type hints, `X | None`. Ruff: line length 100.
- Asynchronous route handlers (`async def`) for `ib_async` on Uvicorn's main loop. Synchronous calls for `futu-api` dispatched via `anyio.to_thread.run_sync()`.
- Query parameters preferred over URL path inline parameters for resource filtering.
- Standardized broker translation philosophy:
  - Backend absorbs broker complexities, connection protocols, and format discrepancies.
  - Strict Enums (`Currency`, `Exchange`, `SecurityType`, `OptionType`) enforce loud failure when new/unmapped symbols, exchanges, or security types are encountered.
  - All models inherit from `UninvModel`: every string field is automatically stripped and consecutive spaces collapsed to a single space.
  - Raw numerical preservation: zero rounding in backend. All prices, values, and calculations preserve raw floats. Rounding is strictly a GUI display concern.
  - `Position` fields:
    - `instrument`: descriptive name (e.g. `NVDA Jan19'29 145 CALL`, `Fund Assets`).
    - `symbol`: local contract symbol (e.g. `BOXX`, `NVDA 290119C00145000`, `US.TSM`).
    - `position`: quantity held (raw float, never rounded).
    - `avg_price`: normalized per-unit entry price.
    - `mark_price`: current per-unit market price.
    - `cost_basis`: backend-computed as `position * avg_price * multiplier`.
    - `market_value`: taken directly from broker portfolio feed.
    - `unrealized_pnl`: taken directly from broker portfolio feed.
    - `multiplier`: contract multiplier.
    - `currency`: typed as `Currency` Enum.
    - `exchange`: primary exchange destination typed as `Exchange | None` Enum.
    - `sec_type`: security type typed as `SecurityType` Enum.
    - `last_trading_date`: expiration date in `YYYY-MM-DD` format.
    - `days_left`: calendar days until expiration (auto-calculated from `last_trading_date` vs current UTC date).
    - `strike`: strike price for options.
    - `option_type`: `OptionType.CALL`, `OptionType.PUT`, or `None`.
  - `AccountValues` fields:
    - Streamlined financial overview: `currency`, `net_liquidation`, `gross_position_value`, `cash_balance` (directly from broker feed: `TotalCashValue` / `cash`), `maint_margin_req`, `excess_liquidity`, `unrealized_pnl`, `cash_balances` (multi-currency list with zero filtering `abs(amt) > 1e-8`).
- Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`; commit `uv.lock`.
- Tests live in `tests/`, using `fastapi.testclient.TestClient`.
