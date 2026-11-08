# Architecture notes

These are the design decisions so far and the reasons behind them. Update this file whenever
one of them changes.

> **Engineering Journal:** For the detailed log of technical trials, dead ends, and why specific approaches (like Client Portal Gateway) were abandoned, see [trials_and_errors.md](trials_and_errors.md).

## 1. Python owns the business logic; Rust stays thin

Most broker SDKs and financial libraries (IBKR `ib_async`, Futu OpenAPI, pandas, options
pricing) are Python-first, and the main developer works in Python. So all portfolio logic
lives in `backend/`. The Rust side of the Tauri app only:

- opens the native window, and
- forwards UI requests to the backend through **one generic command**, `api_get(path)`.

This means new features usually only touch Python (endpoint) and JS (UI). Rust changes are
only needed for native features such as the system tray, notifications, auto-update, or
starting the backend process.

The proxy only allows `/api/...` and `/health` paths, so the webview can't use it to reach
arbitrary URLs.

## 2. Shared models are the contract

`backend/src/uninv_backend/models.py` is the single source of truth for all data shapes across
brokers:

- **Strict Enums for Loud Failure:** `Currency`, `Exchange`, `SecurityType`, and `OptionType`.
  When an unsupported exchange, currency, or asset class is encountered, it fails loudly and
  visibly during validation rather than passing corrupt or unhandled data downstream.
- **Unified Snapshot Models:**
  - `AccountsResponse`: broker ID, UTC `asof` timestamp, and list of account IDs.
  - `BrokerAccountSnapshot`: unified financial overview (`AccountValues`), holdings (`Position` list),
    and UTC `asof` timestamp.
  - `AccountValues`: account-wide non-BASE financial ledger streamlined for "current portfolio status"
    (net liquidation, gross position value, maintenance margin, excess liquidity, unrealized P&L, and
    multi-currency cash balances with strict zero-filtering). Redundant or order-entry fields (buying power,
    available funds, initial margin req, single scalar cash balance) are omitted.
  - `Position`: standardized instrument fields (`instrument`, `symbol`, `avg_price`, `mark_price`,
    `cost_basis`, `market_value`, `unrealized_pnl`, `multiplier`, `sec_type`, `option_type`, `last_trade_date`).
    Supports nullable fields for aggregate line items (e.g. unbundled Fund Assets / Bond Assets where
    underlying holdings cannot be individually retrieved from broker daemons).
  - `FxMatrixResponse`: supported currencies list, UTC `asof` timestamp, and full (11x11) rates matrix.
- **Normalization with `UninvModel`:** Every string is automatically stripped and internal double-spaces
  (e.g., OCC option symbols like `"NVDA  290119C00145000"`) are collapsed to single spaces.
- **Raw Numerical Precision:** Zero rounding in the backend. All prices, quantities, and cash totals preserve
  full raw float precision. Rounding is strictly a GUI presentation concern.
- The Rust shell passes JSON payloads through untouched (`serde_json::Value`).

## 3. Pluggable broker connectors & standardized feeds

The backend completely abstracts broker-specific connection protocols, authentication quirks,
and feed discrepancies into standard RESTful endpoints:

- `GET /api/v1/supporting-brokers`: list of configured brokers (`ibkr`, `futu`).
- `GET /api/v1/accounts?broker_id={id}`: active accounts for the broker.
- `GET /api/v1/snapshot?broker_id={id}&account_id={id}`: live account snapshot.

**Broker Account Hierarchy & Meta-Broker Architecture:**
- **Interactive Brokers (IBKR):** IBKR operates with a single unified account container (`U...`) encompassing all security types, currencies, and products.
- **Futu as a Meta-Broker:** Futu operates as a meta-broker managing multiple independent subsidiaries (`FUTUSECURITIES` for Futubull HK, `FUTUINC` for Moomoo US, `FUTUSG`, `FUTUAU`, etc.) and separate trade contexts (`OpenSecTradeContext`, `OpenFutureTradeContext`, `OpenCryptoTradeContext`). `uninv` normalizes these at the **Universal Account level** (`uni_card_num`). Queries traverse all trade contexts (with `filter_trdmarket=TrdMarket.NONE` for securities) and loop over all `SecurityFirm` enum values to consolidate underlying physical sub-accounts into their parent universal container.
- **Unbundled Fund & Bond Assets:** When broker daemons like OpenD report aggregate fund/bond wealth values (`fund_assets`, `bond_assets`) without underlying holdings breakdown, `uninv` unbundles them into synthetic position rows (`Fund Assets`, `Bond Assets`) with `market_value` set to the balance, preserving mathematical ledger balance without loss of asset visibility.

**Zero-Cache Guarantee:** Snapshot endpoints never cache broker data in-memory. Every refresh request
queries the live broker daemon to capture an authentic, 100% real-time snapshot of account values and holdings.
External network calls are guarded by strict asynchronous timeouts (e.g., 3–4 seconds) to guarantee the backend
remains responsive even if a broker daemon is busy.

## 4. Global data pulling & FX matrix architecture

Converting multi-currency holdings across different broker accounts requires a robust, zero-latency
currency conversion layer:

- **Unified FX Matrix (`/api/v1/fx`):** Instead of requesting individual currency pairs on demand, the backend
  returns a full 11x11 conversion matrix (`rates[from_currency][to_currency]`) covering all 11 supported
  currencies (`USD`, `HKD`, `EUR`, `GBP`, `JPY`, `CAD`, `AUD`, `CHF`, `CNH`, `SGD`, `NZD`).
- **Graph-Based Pathfinding (`FxRouter`):** Direct exchange rates are fetched from IBKR IDEALPRO. An in-memory
  Breadth-First Search (BFS) graph router automatically synthesizes reciprocal rates (`1 / rate`) and multi-hop
  cross-rates (e.g. `CAD` $\to$ `USD` $\to$ `EUR`) for missing pairs.
- **Decoupled FX Engine:** Currently, TWS acts as the live FX pricing engine for the entire application.
  The FX interface is decoupled from broker connectors: future FX providers (such as an external REST API,
  Futu FX, or a central bank feed) can plug into `FxRouter` by simply satisfying the matrix interface,
  without touching any UI code or broker models.
- **Global Pull & Instant Client-Side Switching:** The frontend pulls broker snapshots and the FX matrix
  together on load/refresh, fixing the dataset in memory. Switching the display currency in the headbar
  recalculates all portfolio metrics instantly client-side with **zero additional network calls**.

## 5. Groups

Groups are user-defined sets of positions that can span brokers. A position can belong to
several groups, which is why group weights don't sum to 100%. Groups reference positions by
`Position.id = "<account_id>:<symbol>"`. They're hardcoded in `portfolio/groups.py` until we
add local persistence (SQLite) and editing in the UI.

## 6. Frontend: no build step

The UI is plain HTML/CSS/ES-module JavaScript in `desktop/src`. No Node.js, no bundler. The
same files run in the Tauri window (requests go through Rust) or in a normal browser (requests
go straight to the backend, which allows CORS from `localhost:1420`). If the UI grows large
(e.g. the option strategy builder with charts), consider moving to Vite + TypeScript. Tauri
supports that by setting `build.devUrl` / `beforeDevCommand` in `tauri.conf.json`.

## 7. Process model (current → planned)

- **Now (dev):** backend and desktop app run as two processes orchestrated by `scripts/start-all.ps1`
  (or `start-all.cmd`) on Windows, and `scripts/start-all.sh` on macOS/Linux. Alternatively,
  run independently via `start-backend` and `start-desktop`.
- **Planned (release - Desktop):** package the backend with PyInstaller as a Tauri
  [sidecar](https://v2.tauri.app/develop/sidecar/). Tauri starts it on launch, picks a free
  port and stops it on exit, so desktop users get a single installer.

## 8. Cross-Platform Target & Standalone Broker Architecture (Windows, macOS, Linux)

uninv supports **Windows, macOS, and Linux**:

- **Standalone Broker Daemons:** Broker gateways (such as **IB Gateway** from Interactive Brokers and **OpenD** from Futu) run as standalone applications on the host machine. This gives users full native support for modern biometric passkeys (Windows Hello, Apple Touch ID), hardware FIDO2 keys, and 2FA prompts during login.
- **Why Client Portal Gateway Was Discarded:** IBKR rolled out mandatory passkeys on user accounts, but failed to update their legacy Client Portal Web API gateway (`clientportal.gw`) login page to support WebAuthn / Passkeys. This completely locks out passkey-enabled users. In contrast, standalone IB Gateway natively handles passkeys on the OS desktop.
- **Socket Interfaces:** Once authenticated, gateways expose local TCP socket APIs (`127.0.0.1:4001` for IB Gateway, `127.0.0.1:11111` for Futu OpenD). The `uninv` Python backend connects asynchronously using `ib_async` and `futu-api`.
- **Cross-Platform CI Matrix:** Tested on `windows-latest`, `macos-latest`, and `ubuntu-latest` for both the Python FastAPI backend and the Tauri 2 desktop shell.

## 9. Asyncio Event Loop & Threading Architecture (Single Loop vs Threadpool Coexistence)

Understanding Python's event loop and FastAPI's threadpool dispatching is critical when integrating
different broker SDKs:

```
                            ┌──────────────────────────────────────────────┐
                            │            FastAPI (Uvicorn Process)          │
                            └──────────────────────┬───────────────────────┘
                                                   │
                        ┌──────────────────────────┴──────────────────────────┐
                        │                                                     │
           [async def route handlers]                             [def route handlers]
                        │                                                     │
                        ▼                                                     ▼
        ┌───────────────────────────────┐                     ┌───────────────────────────────┐
        │   Uvicorn Main Event Loop     │                     │     AnyIO Threadpool Worker   │
        │       (Single Thread)         │                     │     (Dedicated OS Thread)     │
        ├───────────────────────────────┤                     ├───────────────────────────────┤
        │ - Handles /snapshot (IBKR)    │                     │ - Handles /snapshot (Futu)    │
        │ - Handles /fx (TWS batch)     │                     │ - Runs blocking futu-api SDK  │
        │ - Holds stateful TCP socket   │                     │ - Blocks only its own thread  │
        │ - Zero thread hops or locks   │                     │ - Never blocks main loop      │
        └───────────────────────────────┘                     └───────────────────────────────┘
```

1. **Native `async def` for Stateful Async Sockets (`ib_async`):**
   - An OS TCP socket registered in an `asyncio` event loop has **strict thread affinity** with that loop.
   - Route handlers that interact with `ib_async` (`/api/v1/snapshot?broker_id=ibkr`, `/api/v1/fx`) are declared as `async def`.
   - FastAPI executes `async def` routes directly on Uvicorn's main thread and primary event loop.
   - Sockets, request futures, and responses all resolve on this single loop. This completely avoids cross-thread socket deadlocks without needing custom locks or background worker threads.

2. **Standard `def` for Blocking Synchronous SDKs (`futu-api`):**
   - Certain broker SDKs (such as Futubull's `futu-api`) are inherently synchronous and blocking.
   - When integrating synchronous broker SDKs, their route handlers should be declared with standard `def`:
     ```python
     @router.get("/snapshot")
     def get_futu_snapshot(account_id: str):
         # FastAPI automatically runs this in an anyio worker thread
         return futu_service.get_snapshot(account_id)
     ```
   - FastAPI automatically routes standard `def` handlers to its threadpool. The blocking calls will run safely on a background thread without starving Uvicorn's main event loop or interfering with `ib_async`.

3. **Simplicity Over Scaffolding:**
   - Rather than wrapping libraries in custom thread runners (`_IBRunner`) or threading locks, the architecture lets FastAPI's native routing semantics (`async def` vs `def`) handle the execution context cleanly and idiomatic to Python.

## Repo evolution guideline

Keep the top level split by runtime: `backend/` (Python), `desktop/` (Tauri). When new pieces
appear, add them as siblings rather than nesting:

- a shared Python library used by several services → turn the root into a
  [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with `packages/<name>/`
- larger features inside the backend → new subpackages next to `brokers/` and `portfolio/`
  (e.g. `options/` for the strategy builder, `marketdata/`, `storage/`)
