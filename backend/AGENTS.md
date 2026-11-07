# AGENTS.md: backend (Python / FastAPI)

Rules for `backend/`. Root `AGENTS.md` applies too.

## Layout
- `src/uninv_backend/models.py`: Pydantic models, **the API contract**. Defines `Broker`, `AccountMetadata`, `CashBalance`, and `Position`.
- `src/uninv_backend/data.py`: Central data store holding broker accounts, cash balances, and positions.
- `src/uninv_backend/api/routes.py`: `/api/v1` routes:
  - `GET /api/v1/brokers`
  - `GET /api/v1/accounts/{broker_id}`
  - `GET /api/v1/cash-balance/{broker_id}` (supports `?account_id=...`)
  - `GET /api/v1/positions/{broker_id}` (supports `?account_id=...`)
- `config.py`: `Settings` (env prefix `UNINV_`).
- `app.py`: FastAPI app initialization and CORS setup.

## Conventions
- Python 3.13, full type hints, `X | None`. Ruff: line length 100.
- `Position` fields: `instrument`, `symbol`, `position`, `average_price`, `mark_price`, `currency`, `expiry_date`, and `delivery_date`.
- Position naming conventions:
  - Stock / ETF: descriptive name + ticker (e.g. `Alphabet Inc. Class A`, `GOOGL`).
  - Stock Option: `GOOGL Dec 18 '26 140P`, symbol `GOOGL261218P00140000`, has `expiry_date`.
  - Future: `E-mini S&P 500 Mar 19 '27`, symbol `ESH27`, has `delivery_date`.
  - Futures Option: `E-mini S&P 500 Mar 19 '27 7400P Dec 18 '26`, symbol `ESH27 7400P 261218`, has `expiry_date`.
- Derived figures (market value, cost basis, unrealised P&L) are computed client-side, keeping backend raw and thin.
- Multipliers: Options = 100, ES futures / futures options = 50, NQ futures = 20, equities = 1.
- All values currently in USD; FX conversion handled via active display currency (USD / GBP).
- Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`; commit `uv.lock`.
- Tests live in `tests/`, using `fastapi.testclient.TestClient`.
