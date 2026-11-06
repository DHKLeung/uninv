# Architecture notes

These are the design decisions so far and the reasons behind them. Update this file whenever
one of them changes.

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

`backend/src/uninv_backend/models.py` defines `Account`, `Position`, `PositionGroup` and the
`PortfolioSummary` response. Broker connectors convert their broker's data into these models.
Nothing downstream knows which broker the data came from. The Rust layer passes JSON through
untouched, so the models are defined once, in Python.

## 3. Broker connectors are pluggable

`BrokerConnector` (`brokers/base.py`) is an async interface. `PortfolioService` queries all
connectors concurrently. **If one broker fails, the rest of the portfolio still loads.** The
failure is reported in `PortfolioSummary.errors` and shown as a banner in the UI.

Today `brokers/mock.py` provides simulated IBKR, Futu and Schwab connectors. The test data
covers:

- multiple accounts per broker (Schwab IRA + brokerage),
- multi-currency (HKD account at Futu holding a USD stock),
- the same symbol at two brokers (MSFT at IBKR and Schwab), which shows consolidation,
- options with a contract multiplier (AAPL call).

## 4. Base currency and FX

All totals are converted into `UNINV_BASE_CURRENCY` (default USD) through an `FxProvider`.
For now `StaticFxProvider` uses hardcoded rates; replace it with a live source later.
Positions keep their native currency values as well, and the UI shows both.

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

- **Now (dev):** backend and desktop app run as two processes (`scripts/dev.ps1` starts both).
- **Planned (release):** package the backend with PyInstaller as a Tauri
  [sidecar](https://v2.tauri.app/develop/sidecar/). Tauri starts it on launch, picks a free
  port and stops it on exit, so the user gets a single installer.

## Repo evolution guideline

Keep the top level split by runtime: `backend/` (Python), `desktop/` (Tauri). When new pieces
appear, add them as siblings rather than nesting:

- a shared Python library used by several services → turn the root into a
  [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/) with `packages/<name>/`
- larger features inside the backend → new subpackages next to `brokers/` and `portfolio/`
  (e.g. `options/` for the strategy builder, `marketdata/`, `storage/`)
