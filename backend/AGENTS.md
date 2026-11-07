# AGENTS.md: backend (Python / FastAPI)

Rules for `backend/`. Root `AGENTS.md` applies too.

## Layout
- `src/uninv_backend/models.py`: Pydantic models, **the API contract**. Defines `SupportingBroker`, `CashBalanceItem`, `AccountValues`, and `Position`.
- `src/uninv_backend/ibkr.py`: Synchronous, thread-safe IBKR connector service (`IBKRService`, `ibkr_service`) wrapping `ib_async`. Connects directly to TWS on port 7496. Startup is independent of TWS; endpoints fail gracefully with HTTP 503 and clear error messages when TWS is offline and auto-reconnect once TWS is available.
- `src/uninv_backend/api/routes.py`: `/api/v1` routes using query parameters and synchronous handlers (`def`, run in threadpool):
  - `GET /api/v1/supporting-brokers`
  - `GET /api/v1/accounts?broker_id=ibkr`
  - `GET /api/v1/account-values?broker_id=ibkr&account_id=U16110728`
  - `GET /api/v1/positions?broker_id=ibkr&account_id=U16110728`
- `config.py`: `Settings` (env prefix `UNINV_`).
- `app.py`: FastAPI app initialization and CORS setup.

## Conventions
- Python 3.13, full type hints, `X | None`. Ruff: line length 100.
- Synchronous route handlers (`def` instead of `async def`): FastAPI automatically runs them in a worker threadpool, avoiding event loop conflicts with socket clients.
- Query parameters are preferred over URL path inline parameters.
- Pure broker data philosophy:
  - Backend absorbs broker complexities, connection protocols, and format discrepancies.
  - Backend translates raw broker feeds into our standard data models and serves them cleanly.
  - Derived calculations (e.g. market value, cost basis, unrealised P&L, NLV) are intentionally omitted from backend payloads; clients calculate derived metrics directly:
    - `cost_basis = position * average_price * multiplier`
    - `market_value = position * market_price * multiplier`
    - `unrealized_pnl = (market_price - average_price) * position * multiplier`
- `Position` fields:
  - `instrument`: descriptive name (resolved via contract details `longName`).
  - `symbol`: local contract symbol (from `localSymbol`, e.g. `BOXX`, `EW3Z6 P7400`, `GOOGL 290119C00230000`).
  - `sec_type`: security type (`STK`, `OPT`, `FOP`, `CRYPTO`, etc.).
  - `position`: quantity held.
  - `average_price`: normalized per-unit entry price.
  - `market_price`: current per-unit market price.
  - `multiplier`: contract multiplier (1.0 for STK, 100.0 for stock options, 50.0 for ES options).
  - `currency`: trading currency.
  - `primary_exchange`: primary exchange destination (e.g. `BATS`, `ARCA`, `AMEX`, `CME`, `OSL`).
  - `last_trading_date`: expiration or contract date (`YYYYMMDD`).
  - `strike`: strike price for options / futures options.
  - `right`: option right (`C` or `P`).
  - `underlying_symbol`: underlying asset symbol.
  - `con_id`: broker contract ID.
- `AccountValues` fields:
  - `available_funds`, `buying_power`, `excess_liquidity`, `maintenance_margin`.
  - `currency`: account base currency.
  - `cash_balances`: list of `CashBalanceItem(currency, amount)` for all held currencies, strictly ignoring IBKR's artificial `BASE` currency.
- Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`; commit `uv.lock`.
- Tests live in `tests/`, using `fastapi.testclient.TestClient`.
