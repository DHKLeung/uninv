# uninv-backend (v1.2.0)

Python 3.13 FastAPI backend for `uninv`, managed with **uv**.

The backend abstracts broker-specific connection protocols, authentication models, and data discrepancies into a clean, standardized RESTful API consumed by the Tauri desktop shell (and web browsers in dev mode).

---

## Commands

Run all commands from the `backend/` directory:

```powershell
uv sync                      # Create virtual environment and install dependencies
uv run uninv-backend         # Start API server on http://127.0.0.1:7541 (auto-reload with --reload)
uv run pytest                # Run test suite
uv run ruff format .         # Format code
uv run ruff check --fix .    # Lint and fix code
```

Once running, interactive API docs are accessible at <http://127.0.0.1:7541/docs>.

---

## Directory Layout

```text
src/uninv_backend/
├── __init__.py        # CLI console entry point (`uv run uninv-backend`)
├── app.py             # FastAPI app factory, CORS middleware, and health check
├── config.py          # Settings management with pydantic-settings (UNINV_ env vars)
├── models.py          # Unified data models and strict StrEnums (single source of truth)
├── ibkr.py            # IBKRService: native asyncio connector wrapping ib_async
├── futu.py            # FutuService: meta-broker connector wrapping futu-api
├── fx.py              # FxRouter: Forex batch quote routing and 11x11 matrix synthesis
└── api/
    ├── __init__.py
    └── routes.py      # REST endpoints under /api/v1
tests/
    └── test_api.py    # Comprehensive test suite (32 tests)
```

---

## Architecture & Design Principles

### 1. Dual Asynchronous Execution Model
- **Native Async (`ib_async`):** Route handlers interacting with Interactive Brokers (`/snapshot?broker_id=ibkr`, `/fx`) are declared as `async def` and execute directly on Uvicorn's main thread and primary event loop. This ensures strict thread affinity for stateful TCP sockets, preventing race conditions or deadlock.
- **Worker Threadpool (`futu-api`):** Synchronous calls to Futu's blocking SDK are executed off the main event loop via `anyio.to_thread.run_sync()`. This isolates blocking network calls in worker threads without starving Uvicorn's event loop.

### 2. Standardized Feed Normalization
- **Strict Enums for Loud Failure:** `Currency`, `Exchange`, `SecurityType`, and `OptionType`. When unexpected symbols or unmapped exchanges are returned by a broker feed, Pydantic validation fails loudly.
- **String Cleaning via `UninvModel`:** Automatically strips leading/trailing spaces and collapses consecutive whitespace into a single space (e.g., normalizing OCC option contract strings like `"NVDA  290119C00145000"` to `"NVDA 290119C00145000"`).
- **Exact Raw Floats:** Numerical fields (`avg_price`, `mark_price`, `cost_basis`, `market_value`, `unrealized_pnl`, `rate`, `position`) preserve raw float precision. Zero rounding is performed in the backend.

### 3. Account Structure Normalization
- **IBKR:** Unified account structure (`U...`) containing all asset types in a single portfolio ledger.
- **Futu as a Meta-Broker:** Consolidates multiple subsidiaries (`FUTUSECURITIES`, `FUTUINC`, `FUTUSG`, etc.) and contexts (`OpenSecTradeContext`, `OpenFutureTradeContext`, `OpenCryptoTradeContext`) under their parent Universal Account (`uni_card_num`).

---

## Endpoints

| Method | Path | Summary |
|---|---|---|
| `GET` | `/health` | Service health status and version |
| `GET` | `/api/v1/supporting-brokers` | List of supported brokers (`ibkr`, `futu`) |
| `GET` | `/api/v1/accounts` | Active account IDs for a broker with UTC `asof` |
| `GET` | `/api/v1/snapshot` | Unified snapshot (`AccountValues` + `Position` list) with completion `asof` |
| `GET` | `/api/v1/fx` | 11×11 foreign exchange rates matrix |
| `GET` | `/api/v1/broker-connection-test` | Test connectivity to a broker gateway |
| `GET` | `/api/v1/broker-gateway-config` | Read configured Host/IP and Port for broker gateways |
| `POST` | `/api/v1/broker-gateway-config` | Dynamically update Host/IP and Port for a broker gateway |
