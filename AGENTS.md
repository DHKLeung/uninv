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

- ✅ Backend rewritten to streamlined Pydantic v2 architecture:
  - Brokers: `Interactive Brokers (Hong Kong)` (`ibkr-hk`) and `Futubull (Hong Kong)` (`futubull-hk`).
  - Accounts metadata: `IBKR-HK (0728)`, `Futubull-HK (7283)`, `Futubull-HK (7612)`, `Futubull-HK (0281)`.
  - Positions: mock data across stocks, ETFs, futures (with delivery date), stock options (with expiry date), futures options (with expiry date), Bitcoin, and money market funds (e.g. `ChinaAMC Select USD Money Market Fund` HK0000923844). Raw broker fields only; derived metrics (market value, cost basis, unrealised P&L) computed in frontend.
  - Clean endpoints: `GET /api/v1/brokers`, `GET /api/v1/accounts/{broker_id}`, `GET /api/v1/cash-balance/{broker_id}`, `GET /api/v1/positions/{broker_id}`.
  - All 12 backend tests pass, Ruff check passes.
- ✅ GUI Application updated:
  - Configured for 16:9 1600×900 default display layout (`tauri.conf.json` and responsive CSS).
  - Navigation tab header with `Portfolio` active tab.
  - British English KPI cards: `NET LIQUIDATION VALUE`, `POSITION VALUE`, `CASH BALANCE`, `UNREALISED P&L` (with % and no "on cost").
  - Top right: As-of timestamp, currency selector (USD `$` and GBP `£` at 0.7487 FX rate), refresh button.
  - Accounts section: Account cards displaying `NET LIQUIDATION VALUE`, `POSITION VALUE`, `CASH BALANCE`, and `UNREALISED P&L`, with quick-filter click support.
  - Holdings & Balances section: Big unified section with account filter pills (`All`, `IBKR-HK (0728)`, etc.) and two subsections:
    1. Positions: search box, count badge, and 12-column table (with Expiry Date, Delivery Date, Cost Basis, and Market Value).
    2. Cash Balances: displays associated account, broker, account number, currency, and cash balance.
  - Removed obsolete simulated badge, allocation panels, and groups.
- ✅ Rust shell compiles cleanly (`cargo check`).
- ✅ Shifted to Standalone Broker Daemon Architecture (Cross-Platform):
  - Client Portal Gateway abandoned due to IBKR passkey authentication limitations.
  - Broker gateways (IB Gateway / TWS, Futu OpenD) run standalone on the host OS, supporting native passkeys and 2FA across Windows, macOS, and Linux.
  - Added `gateways/ib_gateway/instruction.md` setup and configuration guide.
  - Cross-platform CI matrix (`windows-latest`, `macos-latest`, `ubuntu-latest`) and runner scripts (`dev.ps1`, `dev.cmd`, `dev.sh`) enabled.
  - Integrated `ib_async` into backend dependencies for high-performance asyncio socket communication.
  - Next: Build live IBKR connector service in `backend/src/uninv_backend/` to query IB Gateway on port 4001/7496.

### Next steps
1. Real broker connector integrations (IBKR / Futubull).
2. Live market data and live FX rate pulling.
3. PyInstaller sidecar bundling for single-installer desktop deployment.
