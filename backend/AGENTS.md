# AGENTS.md: backend (Python / FastAPI)

Rules for `backend/`. Root `AGENTS.md` applies too.

## Layout
- `src/uninv_backend/models.py`: Pydantic models with strict `StrEnum`s (`Currency`, `Exchange`, `SecurityType`, `OptionType`). Defines `AccountsResponse`, `BrokerAccountSnapshot`, `AccountValues`, `Position`, `FxRate`, `SupportingBroker`.
- `src/uninv_backend/ibkr.py`: Synchronous, thread-safe IBKR connector service (`IBKRService`, `ibkr_service`) wrapping `ib_async`. Connects directly to TWS on port 7496. Provides `get_snapshot`, `get_fx_rate`, and auto-reconnection.
- `src/uninv_backend/api/routes.py`: `/api/v1` routes:
  - `GET /api/v1/supporting-brokers`
  - `GET /api/v1/accounts?broker_id=ibkr`: returns `AccountsResponse` with UTC `asof` timestamp.
  - `GET /api/v1/snapshot?broker_id=ibkr&account_id=U16110728`: returns `BrokerAccountSnapshot` with UTC `asof` timestamp.
  - `GET /api/v1/fx?base=EUR&quote=USD`: returns `FxRate` with UTC `asof` timestamp.
- `config.py`: `Settings` (env prefix `UNINV_`).
- `app.py`: FastAPI app initialization and CORS setup.

## Conventions
- Python 3.13, full type hints, `X | None`. Ruff: line length 100.
- Synchronous route handlers (`def` instead of `async def`): FastAPI automatically runs them in a worker threadpool, avoiding event loop conflicts with socket clients.
- Query parameters are preferred over URL path inline parameters.
- Standardized broker translation philosophy:
  - Backend absorbs broker complexities, connection protocols, and format discrepancies.
  - Strict Enums (`Currency`, `Exchange`, `SecurityType`, `OptionType`) enforce loud failure when new/unmapped symbols, exchanges, or security types are encountered.
  - `Position` fields:
    - `instrument`: descriptive name. Precise formatting for derivatives (e.g. `NVDA Jan19'29 145 CALL`, `ES FOP(EW3) Dec18'26 7400 PUT`), resolved company `longName` for stocks.
    - `symbol`: local contract symbol (`localSymbol`, e.g. `BOXX`, `EW3Z6 P7400`, `GOOGL 290119C00230000`).
    - `position`: quantity held.
    - `avg_price`: normalized per-unit entry price.
    - `mark_price`: current per-unit market price.
    - `cost_basis`: backend-computed as `position * avg_price * multiplier`.
    - `market_value`: taken directly from broker portfolio feed.
    - `unrealized_pnl`: taken directly from broker portfolio feed.
    - `multiplier`: contract multiplier (1.0 for STK, 100.0 for stock options, 50.0 for ES options).
    - `currency`: typed as `Currency` Enum.
    - `exchange`: primary exchange destination typed as `Exchange | None` Enum.
    - `sec_type`: security type typed as `SecurityType` Enum.
    - `last_trade_date`: expiration date in `YYYY-MM-DD` format.
    - `strike`: strike price for options.
    - `option_type`: `OptionType.CALL`, `OptionType.PUT`, or `None`.
  - `AccountValues` fields:
    - Account-wide totals (strictly non-BASE): `currency`, `available_funds`, `buying_power`, `cash_balance`, `cash_balances` (multi-currency list), `equity_with_loan_value`, `excess_liquidity`, `gross_position_value`, `init_margin_req`, `maint_margin_req`, `net_liquidation`, `unrealized_pnl`.
- Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`; commit `uv.lock`.
- Tests live in `tests/`, using `fastapi.testclient.TestClient`.
