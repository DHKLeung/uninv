# AGENTS.md: uninv

Guidance for AI coding agents working in this repo. Read this first. **Keep it current.** At
the end of any task that changes structure, commands, conventions, decisions or status, update
the relevant section here (or in the nested `backend/AGENTS.md` / `desktop/AGENTS.md`). That is
part of finishing the task, not optional. Keep it short: rules and facts only. Long
explanations go in `docs/`.

## Project

**uninv** (unified investing: **uni**fied + **inv**esting) is a desktop app that shows one combined portfolio across several
broker accounts, plus user-defined groups of positions that can span brokers. Later: option
strategy builder, live prices, etc. (roadmap in `README.md`).

- `backend/`: Python 3.13 + FastAPI, managed with **uv**. All business logic: broker
  accounts metadata and positions. → see `backend/AGENTS.md`
- `desktop/`: **Tauri 2** app (16:9 1600x900 default). `src/` = plain HTML/CSS/JS UI (no Node, no bundler);
  `src-tauri/` = thin Rust shell. → see `desktop/AGENTS.md`
- `gateways/`: Documentation and setup guides for external broker daemons (`gateways/tws/instruction.md`, `gateways/futu_gateway/instruction.md`). Broker gateways run standalone on the host OS.
- `docs/architecture.md`: design decisions and the reasons for them. Update it when a decision
  changes.
- `docs/trials_and_errors.md`: log of technical trials, dead ends, and why specific approaches failed.
- `scripts/start-all.ps1`: orchestrates running backend + desktop app together on Windows (`-Browser` for browser UI; one-click `scripts/start-all.cmd`).
- `scripts/start-backend.ps1`: runs backend only on Windows (`scripts/start-backend.cmd`).
- `scripts/start-desktop.ps1`: runs desktop app on Windows (`-Browser` for browser UI; `scripts/start-desktop.cmd`).
- `scripts/start-all.sh`, `scripts/start-backend.sh`, `scripts/start-desktop.sh`: macOS/Linux equivalents for bash/zsh.

Data flow: UI → `invoke("api_get", {path})` → Rust proxy → `http://<host>:7541/api/v1/...` →
FastAPI.

## Target platforms

**Cross-platform: Windows, macOS, and Linux (Ubuntu).**
- **Desktop:** Tauri 2 desktop shell using native webviews (WebView2 on Windows, WebKit on macOS, WebKitGTK on Linux); Python backend runs locally (sidecar).
- **Broker Gateways:** Standalone daemons (Trader Workstation / TWS on port 7496, Futu OpenD on port 11111) run natively on the host OS, handling passkey/2FA authentication independently. `uninv` connects locally via socket APIs (`ib_async`, `futu-api`).
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
cd backend; uv run uninv-backend --reload   # API :7541, docs at /docs
cd backend; uv run pytest                   # tests (must pass before commit)
cd backend; uv run ruff format .; uv run ruff check --fix .
.\scripts\start-all.ps1                     # one-click: backend + desktop app (or .\scripts\start-all.cmd)
.\scripts\start-all.ps1 -Browser            # one-click: backend + UI in browser (127.0.0.1:1420)
.\scripts\start-backend.ps1                 # backend only (or .\scripts\start-backend.cmd)
.\scripts\start-desktop.ps1                 # desktop only (or .\scripts\start-desktop.cmd)
cd desktop\src-tauri; cargo tauri dev       # or `cargo run` (backend must be running)
cd desktop\src-tauri; cargo tauri build     # production installer (.msi / .exe)
```

**Agent shell quirk:** each command runs in a fresh shell that may not have uv/cargo on PATH.
Prefix with
`$env:Path = "$env:USERPROFILE\.local\bin;$env:USERPROFILE\.cargo\bin;$env:Path";`.

**UI check without a GUI:** serve `desktop/src` on :1420 (see `start-all.ps1 -Browser`) with the
backend running, then
`msedge --headless=new --window-size=1400,1500 --virtual-time-budget=5000 --screenshot=<png> http://127.0.0.1:1420/`
(Edge is at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`).

## Definition of done

- `uv run pytest` and `uv run ruff check .` pass. Add or adjust tests for backend changes.
- UI changes checked (screenshot or running app).
- README / `docs/architecture.md` / this file updated if behaviour, commands or structure changed.
- Commit messages: short imperative subject, body listing notable changes.

## Current status (update this section as work progresses)

_Last updated: 2026-11-09_

- ✅ Backend rewritten to standardized broker feed and unified snapshot model:
  - Abstracted all broker complexity into FastAPI: backend translates raw broker feeds into uninv unified models with strict Enums for loud failure on new items.
  - Enums defined: `Currency` (USD, HKD, EUR, etc.), `Exchange` (BATS, ARCA, NASDAQ, AMEX, NYSE, CME, OSL, IDEALPRO, etc.), `SecurityType` (STOCKS, OPTIONS, FUTURES, FUTURES OPTIONS, CRYPTO, CASH), and `OptionType` (CALL, PUT).
  - `SecurityType.FUTURES_OPTIONS` value is `"FUTURES OPTIONS"` (with space) directly in the Enum.
  - Endpoints converted to query parameters and synchronous handlers (`def`, run in FastAPI threadpool):
    - `GET /api/v1/supporting-brokers`: returns `[{"id": "ibkr", "name": "Interactive Brokers"}]`.
    - `GET /api/v1/accounts?broker_id=ibkr`: returns `AccountsResponse` dict `{"broker_id": "ibkr", "asof": "...", "accounts": ["U1234567"]}`.
    - `GET /api/v1/snapshot?broker_id=ibkr&account_id=U1234567`: unified account snapshot combining account-wide margins/cash (`AccountValues`), open holdings (`Position` list), and UTC `asof` timestamp.
    - `GET /api/v1/currencies`: returns list of all 11 supported currency codes (`USD`, `HKD`, `EUR`, `GBP`, `JPY`, `CAD`, `AUD`, `CHF`, `CNH`, `SGD`, `NZD`).
    - `GET /api/v1/fx?base=EUR&quote=USD`: live FX exchange rate resolved via graph routing with in-memory caching, reciprocal/multi-hop pathfinding, and UTC `asof` timestamp.
  - `FxRouter` in `backend/src/uninv_backend/fx.py`:
    - Graph-based pathfinding across all currency pairs using Breadth-First Search (BFS).
    - Traverses direct IDEALPRO pairs, inverted quotes (`1 / rate`), and multi-hop paths through major hubs (`USD`, `EUR`, `GBP`, etc.) or crosses.
    - Self-healing: if an edge fails to produce a market quote, it is blocked and an alternative path is searched automatically.
  - `Position` model:
    - Standardized fields: `avg_price`, `mark_price`, `cost_basis` (computed by backend as `position * avg_price * multiplier`), `market_value` (directly from API feed), `unrealized_pnl` (directly from API feed), `exchange`, `sec_type`, `option_type`, `last_trade_date` (in `YYYY-MM-DD` format).
    - Precision instrument names for derivatives: e.g. `NVDA Jan19'29 145 CALL` and `ES FOP(EW3) Dec18'26 7400 PUT` (matching TWS on-screen format).
    - Removed unused `con_id` and `underlying_symbol`.
    - Strings guarded by `UninvModel` (collapsed to 1 space, stripped, fixing OCC double-spaced `localSymbol`).
    - Raw numbers: zero rounding in backend; full raw float precision preserved.
  - `AccountValues` model:
    - Account-wide totals (non-BASE, explicit currency): `available_funds`, `buying_power`, `cash_balance`, `cash_balances` (multi-currency list), `equity_with_loan_value`, `excess_liquidity`, `gross_position_value`, `init_margin_req`, `maint_margin_req`, `net_liquidation`, `unrealized_pnl`.
  - `IBKRService` in `backend/src/uninv_backend/ibkr.py` connects directly to TWS on port 7496 with `readonly=True` (connects in ~0.1s), client ID retry resilience, pure native `asyncio` execution on Uvicorn's main loop (zero manual threading/locks), strict network timeouts on Forex batch probes and contract qualification, and zero endpoint caching (every request returns a completely fresh, live snapshot).
  - All 22 backend tests pass, Ruff check passes, Tauri `cargo check` passes.
- ✅ Global Data Pulling & Merged FX Matrix Architecture:
  - Unified `/api/v1/fx` endpoint returns `FxMatrixResponse` containing `asof` timestamp, `currencies` list, and full (11x11) `rates` conversion matrix (`rates[from][to]`).
  - Removed separate `/api/v1/currencies` and pair-level endpoints; single batch fetch in backend against IBKR IDEALPRO pairs with in-memory reciprocal and cross-rate synthesis.
  - Global pull: desktop app pulls broker snapshots and FX matrix once on load/refresh, fixing the dataset in memory.
  - Instantaneous GUI currency switching: selecting a currency in the headbar performs instant local recalculation using the fixed in-memory matrix with zero additional network requests.
  - Unidirectional Portfolio reaction path: Section 1 Accounts Tiles is the sole selector -> updates Section 1 visual highlight -> updates Section 2 Metrics Board -> updates Section 3 Holdings.
- ✅ Full UI Rework Implemented & Verified:
  - Global Headbar: perfectly centered logo/brand ("u" icon + `uninv`), with right-aligned UTC `asof` timestamp, multi-currency selector (11 currencies), and Refresh button. Clean layout spacer on the left keeps center brand mathematically centered.
  - Static Sidebar: 5 navigation items (`Portfolio`, `DCA Planning`, `Option Strategies`, `Settings`, `About`) with live backend status indicator at the bottom.
  - Portfolio Page Structured into 3 Core Sections:
    1. **Accounts**: Top horizontal section displaying account tiles. Default active tile is "All Accounts" (consolidated totals), followed by individual broker account tiles. Clicking a tile highlights it and filters all metrics and holdings down to that account (or back to "All").
    2. **Metrics Board**: Unified consolidated/account-level financial overview board (no chunky card tiles). Features hero metrics (Net Liquidation Value, Unrealized P&L with % return badge, Equity with Loan Value) and a structured hairline metrics grid (Cash Balance, Gross Position Value, Available Funds, Buying Power, Excess Liquidity, Initial Margin Req, Maint Margin Req) dynamically converted into the chosen display currency.
    3. **Holdings**: Two dedicated subsections:
       - **Positions**: Table with symbol, precision instrument name, styled security badges (`STOCKS`, `OPTIONS`, `FUTURES OPTIONS`), exchange, expiry, cost basis, market value, unrealized P&L, search filter box, and interactive column sorting.
       - **Cash Balances**: Table showing multi-currency cash balances with raw amounts and converted balances.
  - Subpage Routing: Clicking sidebar navigation switches smoothly between the live `Portfolio` view and upcoming subpages (`DCA Planning`, `Option Strategies`, `Settings`, `About`).
  - About Subpage: Explains `uninv` meaning (**uni**fied + **inv**esting), version 0.1.0, architecture, and technology stack.
- ✅ Clean scripts in `scripts/`:
  - `start-all` (`.ps1`, `.cmd`, `.sh`): launches backend + desktop app together with clean shutdown on exit. Uses `/health` verification and `-State Listen` TCP checks to prevent false-positive skips caused by Windows `TIME_WAIT` sockets.
  - `start-backend` (`.ps1`, `.cmd`, `.sh`): launches FastAPI server only with auto-cleanup of unresponsive listeners on port 7541.
  - `start-desktop` (`.ps1`, `.cmd`, `.sh`): launches Tauri desktop app (or `-Browser` mode).
- ✅ Standalone Broker Daemon Architecture:
  - TWS verified and connected via socket API on port 7496.
  - Cross-platform runners and setup guides documented in `gateways/tws/instruction.md` and `docs/trials_and_errors.md`.
- ✅ Futubull Integration via `futu-api` (Futu OpenD):
  - Added official `futu-api` package (v10.12.7208).
  - Built `backend/src/uninv_backend/futu.py` (`FutuService`, `futu_service`) connecting to Futu OpenD on port 11111 with fast TCP socket pre-flight probing (`is_opend_available`), preventing `futu-api`'s infinite reconnect loop when OpenD is offline.
  - Multi-context architecture: seamlessly manages `futu.OpenSecTradeContext` (equities, options, funds), `futu.OpenCryptoTradeContext` (cryptocurrency holdings like `CC.BTC`), and `futu.OpenFutureTradeContext` (futures).
  - Robust float parser (`_safe_float`) protects against Futu's string `"N/A"` or null returns on inactive/non-applicable balance items.
  - Native USD conversion support: Futu's `accinfo_query(currency="USD")` directly converts multi-currency asset values and margin requirements using Futu's real-time internal rates.
  - Non-blocking execution via `anyio.to_thread.run_sync()`, isolating Futu's synchronous SDK in FastAPI's threadpool without blocking Uvicorn's main `asyncio` event loop or IBKR sockets.
  - Normalizes US and HK stock, option, and crypto positions, contract multipliers, expiration dates, and multi-currency cash balances (`hk_cash`, `us_cash`, `cn_cash`, `jp_cash`, etc.) into unified `BrokerAccountSnapshot` models.
  - Verified live connection against Futu OpenD: successfully pulls real margin accounts (`TSM`, `SPYM`, `QQQM`, `ASML`) and crypto accounts (`BTC`).
  - Tested with 29 comprehensive unit tests across IBKR and Futu; setup guide documented in `gateways/futu_gateway/instruction.md`.

- ✅ Streamlined Portfolio Snapshot & Futu Meta-Broker Architecture:
  - Redefined `AccountValues` to focus purely on "current portfolio status", dropping order-entry fields:
    - Kept: `currency` (base USD), `net_liquidation`, `gross_position_value`, `maint_margin_req`, `excess_liquidity`, `unrealized_pnl`, `cash_balances` (multi-currency list).
    - Dropped: `available_funds`, `buying_power`, `init_margin_req`, `cash_balance` (single scalar), `equity_with_loan_value`.
    - Strict zero filtering on cash balances: preserves fractional dust (`abs(amt) > 1e-8`), ignores true zero balances.
  - Futu as a Meta-Broker:
    - Broker name standardized to `Futu` (supporting-brokers endpoint returns `[{"id": "ibkr", "name": "Interactive Brokers"}, {"id": "futu", "name": "Futu"}]`).
    - Operates at the **Universal Account level** (`uni_card_num`), e.g. `...1001`, `...1002`, `...2001`, `...2002`.
    - Traverses all 3 contexts: `OpenSecTradeContext(filter_trdmarket=TrdMarket.NONE)` (disabling silent HK filtering), `OpenFutureTradeContext`, `OpenCryptoTradeContext`.
    - Automatically loops over all `SecurityFirm` enum values (`FUTUSECURITIES`, `FUTUINC`, `FUTUSG`, `FUTUAU`, `FUTUCA`, `FUTUJP`, `FUTUMY`) to ingest both Futubull HK and Moomoo US accounts in ~110ms total.
    - Preserves broker's native instrument name and symbol (e.g. `US.TSM`, `CC.BTC`) without forced symbol stripping.
    - Sets `exchange = None` for crypto when not tied to a stock exchange.
    - Snapshot queries fetch account values with `currency="USD"`, delegating all presentation conversions to `uninv`'s FX matrix and GUI.
  - Desktop GUI Alignment:
    - Metrics Board streamlined to Hero metrics (`Net Liquidation Value`, `Unrealized P&L` + badge) and key grid (`Gross Position Value`, `Maint Margin Req`, `Excess Liquidity`).
    - Account horizontal tiles display clean formatted IDs (e.g. `...1001`, `...1002`, `...2001`).
    - In "All Accounts", positions are displayed additively without forced symbol merging; cash balances are summed across all non-zero currency holdings.
  - 29/29 tests pass, Ruff check passes, Tauri `cargo check` passes, live verified with screenshot.

- ✅ v1.0.0 GUI Rework, Unified Branding, Gateway Port Management & Backend Alignment:
  - Version bumped to `1.0.0` across backend (`pyproject.toml`, `__init__.py`) and desktop (`tauri.conf.json`, `Cargo.toml`).
  - App Icon consistency: unified smooth purple square with "uninv" in center generated across Tauri window icons (`icon.png`, `128x128.png`, `32x32.png`, `icon.ico`), in-app headbar brand, and About page.
  - Headbar & As-of Enhancements:
    - Replaced "Refresh" text button with sleek circular arrow icon button with spinning loading animation.
    - As-of timestamp displays the exact finishing time when all endpoint queries complete.
    - Interactive tooltip next to As-of time displays individual timestamp info for each called endpoint (`/api/v1/fx`, `/api/v1/accounts`, `/api/v1/snapshot`).
    - Backend endpoints (`/api/v1/snapshot`, `/api/v1/accounts`, `/api/v1/fx`) updated to capture `asof` strictly *after* all network fetches and probes finish.
  - Cleaned Navigation:
    - Removed Option Strategies and DCA Planning to focus app strictly on unified retail portfolio view.
    - Active pages: `Portfolio`, `Settings`, `About`.
  - Portfolio Page Refinements:
    - Section 1 Accounts: All Accounts tile shows total accounts and positions count (e.g. `6 accounts · 18 positions`) with converted sum of NLV.
    - Section 2 Account Values:
      - Title: "Account Values", scope subtitle displays `All Accounts Consolidated` or `<account_id> · <broker_name>` without currency badge.
      - 6 structured items in 2 rows:
        - Row 1: `Net Liquidation Value`, `Gross Position Value`, `Cash Balance` (`Cash Balance + Gross Position Value == Net Liquidation Value`).
        - Row 2: `Unrealised P&L` (with % badge), `Maintenance Margin`, `Excess Liquidity`.
      - When All Accounts is selected, `Maintenance Margin` and `Excess Liquidity` display `—` (dash); other totals sum across all accounts.
    - Section 3 Holdings:
      - Positions table (12 columns from left to right): `Broker / Account`, `Instrument / Symbol`, `Type / Exchange`, `Position`, `Avg Price`, `Mark Price`, `Cost Basis`, `Market Value`, `Last Trading Date`, `Unrealised P&L`, `Weight`, `Currency`.
      - Positions and Cash Balances are kept un-aggregated in All Accounts view (each broker account row preserved individually).
      - Cash Balances table: `Broker / Account`, `Currency`, `Amount (RAW)`, `AMOUNT (CONVERTED)`.
      - `last_trading_date` field standardized across backend models and frontend.
  - FX and Currency Display Consistency:
    - Currency selector formatted as `<Code> (<Symbol>)`, e.g. `USD ($)`, `EUR (€)`, `GBP (£)`.
    - Main values always prefixed with currency symbol.
    - Always uniform FX multiplication without conditional branch.
    - Average Price, Mark Price, and RAW cash balance remain in raw native currency.
  - Broker Gateway Configuration & Connectivity:
    - Added `GET /api/v1/broker-connection-test` to test connectivity to broker gateways.
    - Added `GET` and `POST /api/v1/broker-gateway-config` to read and dynamically update gateway Host/IP and TCP ports (superseding old redundant port-only endpoints).
    - Rust proxy added generic `api_post` mirror to `api_get`.
    - Settings page provides Edit/Save buttons, broker enable/disable checkboxes, Host/IP and Port inputs, and live `✓ Connected` status badges.
  - About Page: completely reworked, presenting purple square icon, `uninv`, `Unified Investing`, description, Version: `1.0.0`, and Author: `DHKLeung`.
  - Repo-Wide Cleanup & Documentation:
    - Removed redundant endpoints (`/api/v1/broker-gateway-port`) and models.
    - Updated all project markdown documentation (`README.md`, `backend/README.md`, `backend/AGENTS.md`, `desktop/AGENTS.md`, `docs/architecture.md`, `docs/trials_and_errors.md`, `gateways/ib_gateway/instruction.md`, `gateways/futu_gateway/instruction.md`).
    - 31/31 unit tests pass, Ruff check passes, Tauri `cargo check` passes.

- ✅ v1.1.0 Days Left Column, Auto-Refresh Interval & Port 7541 Migration:
  - Added `DAYS LEFT` column to Positions table located immediately right of `Last Trading Date` (13 columns total).
  - Calculates calendar date difference between today (UTC) and `last_trading_date` for options/futures derivatives; displays em-dash (`—`) for perpetual holdings (stocks, funds, crypto).
  - Auto-calculated in backend `Position` model via `@model_validator(mode="after")` and accompanied by client-side `calculateDaysLeft()` utility in `format.js`.
  - Smart null-at-bottom table column sorting: clicking `DAYS LEFT` sorts derivative contracts by expiration days (ascending or descending) while keeping non-expiring stocks cleanly pinned at the bottom.
  - Colspan dynamically updated to 13 on empty search/filter results.
  - Auto-Refresh Interval Dropdown added to the Headbar immediately to the left of the refresh button:
    - Options: `Manual`, `1 min`, `2 mins`, `5 mins`, `10 mins`.
    - Only clickable when `Manual` is selected; disabled and styled with `not-allowed` / low opacity in automatic modes.
    - Automatic overlap skipping: if a previous refresh is still active when interval triggers, skips cleanly without pile-up.
  - Migrated backend port from `8000` to `7541` across Python config, Tauri Rust proxy, frontend API connector, launcher scripts, and all documentation to prevent collisions with third-party software.
  - 1-Click Fresh Clone Launcher: consolidated in `scripts/start-all.cmd` (auto-bootstraps `uv sync` in `start-all.ps1` if `.venv` is absent).
  - Bumped version to `1.1.0` across backend (`pyproject.toml`, `__init__.py`), desktop (`Cargo.toml`, `tauri.conf.json`), UI (`index.html`), and all documentation.
  - 32/32 tests pass, Ruff format/check pass, Tauri `cargo check` compiles cleanly, verified via headless browser render.
  - Cash Balance Accuracy & Clean Session Broker Defaults:
    - Fixed IBKR cash balance discrepancy: eliminated naive `NetLiquidation - GrossPositionValue` derivative deduction that subtracted short option gross exposures twice, mapping `TotalCashValue` / `CashBalance` directly to `cash_balance`.
    - Client-side Section 2 Cash Balance sums converted balances from `cash_balances` across accounts, matching Section 3 Cash Balances table to the exact penny.
    - Broker checkbox state defaults to all enabled on every application launch without `localStorage` memory across restarts.
    - Settings connection testing (`✓ Connected` vs `✗ Offline`) runs for all brokers regardless of checkbox state; checkboxes control portfolio ingestion in-memory during active session.
- ✅ Repository Structure Audit & Cleanup:
  - Enforced strict top-level split: eliminated root-level launcher scripts (`start-all.bat`, `start-all.cmd`), consolidating all execution and setup scripts strictly inside `scripts/`.
  - Removed duplicate `.bat` wrappers in `scripts/` (`start-all.bat`, `start-backend.bat`, `start-desktop.bat`), preserving `.cmd` for Windows cmd/double-click, `.ps1` for PowerShell, and `.sh` for Unix shells.
  - Standardized `scripts/install-build-tools.bat` to `scripts/install-build-tools.cmd` for consistent `.cmd` script naming.
  - Removed orphaned and unreferenced asset `desktop/app-icon.png`.
  - Cleaned up obsolete `FxRate` model and legacy `Broker` alias in `backend/src/uninv_backend/models.py`.

- ✅ v1.1.0 Sidecar Architecture, Production Installers & GitHub Release Automation:
  - Implemented standalone Python backend sidecar:
    - Added PyInstaller build pipeline with entrypoint `backend/entrypoint.py` supporting frozen execution.
    - Added `scripts/build-all.ps1` and `scripts/build-all.cmd` to automate PyInstaller backend compilation and Tauri installer packaging in one click.
    - Configured `externalBin: ["binaries/uninv-backend"]` in `desktop/src-tauri/tauri.conf.json`.
    - Integrated `tauri-plugin-shell` in `desktop/src-tauri/src/lib.rs` to automatically manage the sidecar lifecycle: detects if port 7541 is already running (e.g. dev mode), spawns `uninv-backend` if not, polls until port 7541 is listening before window interaction, and cleanly terminates the child process on window exit.
  - Built Windows release installers:
    - Successfully compiled `desktop/src-tauri/target/release/bundle/nsis/uninv_1.1.0_x64-setup.exe` (NSIS Installer, 61.20 MiB).
    - Successfully compiled `desktop/src-tauri/target/release/bundle/msi/uninv_1.1.0_x64_en-US.msi` (WiX Windows Installer, 62.74 MiB).
  - Cross-platform release automation via GitHub Actions:
    - Added `.github/workflows/release.yml` targeting `windows-latest` (NSIS `.exe` + `.msi`), `macos-latest` (`.dmg`), and `ubuntu-22.04` (`.deb` + `.AppImage`).
    - Compiles the Python backend on each OS cloud runner via PyInstaller, feeds the host target triple sidecar binary to Tauri, and publishes all release assets to GitHub Releases upon tag push (`v*`) or manual `workflow_dispatch`.
  - Generated full release notes in `RELEASE_v1.1.0.md` detailing all inaugural features across brokers, architecture, FX matrix, portfolio boards, and gateway connectivity.

- ✅ v1.2.0 Sidecar Teardown Resilience, 15-Second Auto-Refresh & Clickable GitHub Repo:
  - Version bumped to `1.2.0` across backend (`pyproject.toml`, `__init__.py`), desktop (`Cargo.toml`, `tauri.conf.json`), UI (`index.html`), and all documentation.
  - Auto-Refresh Interval: added `15 secs` option immediately above `30 secs` in headbar dropdown (`desktop/src/index.html`), supporting `Manual`, `15 secs`, `30 secs`, `1 min`, `2 mins`, `5 mins`, and `10 mins`.
  - About Page: added clickable GitHub repository link `DHKLeung/uninv` targeting `https://github.com/DHKLeung/uninv`. Opens in default system browser in Tauri via new native `open_url` command (falling back to `window.open` in browser mode).
  - Sidecar Teardown Architecture (3-layer defense against orphaned backend processes):
    1. **Process Tree Termination on Exit:** Calling `child.kill()` on Windows only killed the PyInstaller bootloader stub, leaving the extracted child Python process (uvicorn) listening on port 7541. Desktop Rust layer now executes process tree termination (`taskkill /F /T /PID <pid>`) on Windows and `pkill -P` on Unix, ensuring all child and grandchild processes terminate.
    2. **Windows Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`):** The sidecar is assigned to an OS Job Object upon spawn. If the Tauri GUI crashes, hangs, or is killed via Task Manager, the Windows NT kernel automatically and unconditionally terminates all processes within the job object.
    3. **Python Parent Watchdog (`--parent-pid`):** Desktop passes `--parent-pid <tauri_pid>` to `uninv-backend`. A background daemon thread in Python monitors the parent process handle (via `WaitForSingleObject` / `OpenProcess` on Windows or `os.kill(pid, 0)` on Unix) and immediately terminates (`os._exit(0)`) if the parent process dies.
    4. **Lifecycle Hooks:** Sidecar cleanup is triggered on `WindowEvent::CloseRequested`, `WindowEvent::Destroyed`, `RunEvent::ExitRequested`, and `RunEvent::Exit`.
  - 33/33 tests pass, Ruff check/format pass, Tauri `cargo check` passes cleanly.
