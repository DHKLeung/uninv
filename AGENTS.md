# AGENTS.md: uninv

Guidance for AI coding agents working in this repo. Read this first. **Keep it current.** At
the end of any task that changes structure, commands, conventions, decisions or status, update
the relevant section here (or in the nested `backend/AGENTS.md` / `desktop/AGENTS.md`). That is
part of finishing the task, not optional. Keep it short: rules and facts only. Long
explanations go in `docs/`.

## Project

**uninv** (UNified INVesting) is a desktop app that shows one combined portfolio across several
broker accounts, plus user-defined groups of positions that can span brokers. Later: option
strategy builder, live prices, etc. (roadmap in `README.md`).

- `backend/`: Python 3.13 + FastAPI, managed with **uv**. All business logic: broker
  accounts metadata and positions. → see `backend/AGENTS.md`
- `desktop/`: **Tauri 2** app (16:9 1600x900 default). `src/` = plain HTML/CSS/JS UI (no Node, no bundler);
  `src-tauri/` = thin Rust shell. → see `desktop/AGENTS.md`
- `gateways/`: Documentation and setup guides for external broker daemons (`gateways/ib_gateway/instruction.md`). Broker gateways run standalone on the host OS.
- `docs/architecture.md`: design decisions and the reasons for them. Update it when a decision
  changes.
- `docs/trials_and_errors.md`: log of technical trials, dead ends, and why specific approaches failed.
- `scripts/dev.ps1`: runs backend + desktop app on Windows (`-Browser` for browser UI, `-ServicesOnly` for headless backend).
- `scripts/dev.cmd`: Windows cmd/PowerShell wrapper (one-click double-clickable launcher).
- `scripts/dev.sh`: macOS/Linux equivalent for bash/zsh (`--browser`, `--services-only`).
- `scripts/start-services.cmd`: one-click launcher for backend in headless mode.

Data flow: UI → `invoke("api_get", {path})` → Rust proxy → `http://<host>:8000/api/v1/...` →
FastAPI.

## Target platforms

**Cross-platform: Windows, macOS, and Linux (Ubuntu).**
- **Desktop:** Tauri 2 desktop shell using native webviews (WebView2 on Windows, WebKit on macOS, WebKitGTK on Linux); Python backend runs locally (sidecar).
- **Broker Gateways:** Standalone daemons (IB Gateway on ports 4001/7496, Futu OpenD on port 11111) run natively on the host OS, handling passkey/2FA authentication independently. `uninv` connects locally via socket APIs (`ib_async`, `futu-api`).
- **CI Matrix:** Automated via GitHub Actions (`.github/workflows/ci.yml`) on `windows-latest`, `macos-latest`, and `ubuntu-latest` for both Python backend (tests/lint) and Tauri Rust shell (`cargo check`).

## The user

- Strong in **Python**, **does not know Rust**. Prefer putting logic in Python. When Rust
  changes are unavoidable, keep them minimal and comment them with Python comparisons, and
  explain them in plain terms in your reply.
- On Windows (PowerShell). Give PowerShell commands, not bash.
- Wants the agent to manage repo structure, docs and this file without being asked.
- Pushing straight to `origin master` is fine (solo project, no PR flow). Only push
  verified work: tests pass, and the app builds if Rust or the UI changed.

## Hard rules

1. **Rust stays thin.** New features = FastAPI endpoint + JS calling
   `apiGet("/api/v1/...")`. Don't add Rust commands per endpoint; the generic `api_get`
   proxy covers it. Rust is only for native features (tray, notifications, sidecar, updater).
2. **`backend/src/uninv_backend/models.py` is the single source of truth** for data shapes.
   Don't duplicate models in Rust (it passes `serde_json::Value` through) or invent
   fields in JS that the API doesn't return.
3. **Never commit secrets.** Broker credentials will go in the OS keychain or a git-ignored
   `.env`; provide `.env.example` instead.
4. **Simulated data must stay labelled.** `Broker.is_simulated=True` for mocks; the UI shows
   a badge. Never present mock prices as real.
5. Use **uv** for everything Python (`uv add`, `uv run`). Never use bare `pip` or
   `python -m venv`.
6. Keep the top level split by runtime (`backend/`, `desktop/`, `docs/`, `scripts/`). Larger
   backend features become new subpackages (`options/`, `marketdata/`, `storage/`). If a
   second Python package appears, turn the root into a uv workspace (`packages/<name>/`).

## Commands (PowerShell)

```powershell
cd backend; uv sync                         # install deps
cd backend; uv run uninv-backend --reload   # API :8000, docs at /docs
cd backend; uv run pytest                   # tests (must pass before commit)
cd backend; uv run ruff format .; uv run ruff check --fix .
.\scripts\dev.ps1                           # one-click: backend + desktop app (or .\scripts\dev.cmd)
.\scripts\dev.ps1 -Browser                  # one-click: backend + UI at http://127.0.0.1:1420
.\scripts\start-services.cmd                # one-click: backend only (headless)
cd desktop\src-tauri; cargo tauri dev       # or `cargo run` (backend must be running)
cd desktop\src-tauri; cargo tauri build     # installer
```

**Agent shell quirk:** each command runs in a fresh shell that may not have uv/cargo on PATH.
Prefix with
`$env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path";`.

**UI check without a GUI:** serve `desktop/src` on :1420 (see `dev.ps1 -Browser`) with the
backend running, then
`msedge --headless=new --window-size=1400,1500 --virtual-time-budget=5000 --screenshot=<png> http://127.0.0.1:1420/`
(Edge is at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`).

## Definition of done

- `uv run pytest` and `uv run ruff check .` pass. Add or adjust tests for backend changes.
- UI changes checked (screenshot or running app).
- README / `docs/architecture.md` / this file updated if behaviour, commands or structure changed.
- Commit messages: short imperative subject, body listing notable changes.

## Current status (update this section as work progresses)

_Last updated: 2026-11-07_

- ✅ Backend rewritten to standardized broker feed and unified snapshot model:
  - Abstracted all broker complexity into FastAPI: backend translates raw broker feeds into uninv unified models with strict Enums for loud failure on new items.
  - Enums defined: `Currency` (USD, HKD, EUR, etc.), `Exchange` (BATS, ARCA, NASDAQ, AMEX, NYSE, CME, OSL, IDEALPRO, etc.), `SecurityType` (STOCKS, OPTIONS, FUTURES, FUTURES_OPTIONS, CRYPTO, CASH), and `OptionType` (CALL, PUT).
  - Endpoints converted to query parameters and synchronous handlers (`def`, run in FastAPI threadpool):
    - `GET /api/v1/supporting-brokers`: returns `[{"id": "ibkr", "name": "Interactive Brokers"}]`.
    - `GET /api/v1/accounts?broker_id=ibkr`: returns pure account ID strings, e.g. `["U16110728"]`.
    - `GET /api/v1/snapshot?broker_id=ibkr&account_id=U16110728`: unified account snapshot combining account-wide margins/cash (`AccountValues`) and open holdings (`Position` list).
    - `GET /api/v1/fx?base=EUR&quote=USD`: live FX exchange rate from IBKR with in-memory caching and reciprocal/triangulation resolution.
  - `Position` model:
    - Standardized fields: `avg_price`, `mark_price`, `cost_basis` (computed by backend as `position * avg_price * multiplier`), `market_value` (directly from API feed), `unrealized_pnl` (directly from API feed), `exchange`, `sec_type`, `option_type`.
    - Precision instrument names for derivatives: e.g. `NVDA Jan19'29 145 CALL` and `ES FOP(EW3) Dec18'26 7400 PUT` (matching TWS on-screen format).
    - Removed unused `con_id` and `underlying_symbol`.
  - `AccountValues` model:
    - Account-wide totals (non-BASE, explicit currency): `available_funds`, `buying_power`, `cash_balance`, `cash_balances` (multi-currency list), `equity_with_loan_value`, `excess_liquidity`, `gross_position_value`, `init_margin_req`, `maint_margin_req`, `net_liquidation`, `unrealized_pnl`.
  - `IBKRService` in `backend/src/uninv_backend/ibkr.py` connects directly to TWS on port 7496 with `readonly=True` (connects in ~0.1s), thread-safe querying via `threading.Lock`, and in-memory contract name/FX caching.
  - All 16 backend tests pass, Ruff check passes, Tauri `cargo check` passes.
- ⏸️ Desktop GUI temporarily stale (awaiting complete redesign to match new backend data contract).
- ✅ Standalone Broker Daemon Architecture:
  - TWS verified and connected via socket API on port 7496.
  - Cross-platform runners and setup guides documented in `gateways/ib_gateway/instruction.md` and `docs/trials_and_errors.md`.

### Next steps
1. Plan and implement new frontend GUI redesign to consume the new `/api/v1/` endpoints.
2. Futubull integration via `futu-api` (Futu OpenD).
3. Live market data and live FX rate pulling.
