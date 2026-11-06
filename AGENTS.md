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
  connectors, aggregation, FX, groups. → see `backend/AGENTS.md`
- `desktop/`: **Tauri 2** app. `src/` = plain HTML/CSS/JS UI (no Node, no bundler);
  `src-tauri/` = thin Rust shell. → see `desktop/AGENTS.md`
- `docs/architecture.md`: design decisions and the reasons for them. Update it when a decision
  changes.
- `scripts/dev.ps1`: runs backend + desktop app (`-Browser` for UI in a browser, no Rust).
- `scripts/dev.sh`: macOS/Linux equivalent for bash/zsh.

Data flow: UI → `invoke("api_get", {path})` → Rust proxy → `http://<host>:8000/api/v1/...` →
FastAPI → `PortfolioService` → `BrokerConnector`s.

## Target platforms

**Cross-platform: Windows, macOS, Linux, and iOS (iPhone).**
- **Desktop (Windows/macOS/Linux):** Tauri 2 desktop shell; Python backend runs locally (sidecar).
- **Mobile (iOS):** Tauri 2 mobile client connecting to the backend over LAN or HTTPS (iOS sandbox prevents background daemon subprocesses).
- **UI:** Must stay responsive, touch-friendly, and respect iOS safe-area insets.

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
.\scripts\dev.ps1                           # backend + desktop app
.\scripts\dev.ps1 -Browser                  # backend + UI at http://127.0.0.1:1420
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

_Last updated: 2026-11-06_

- ✅ Backend scaffolded and tested: simulated IBKR / Futu / Schwab (4 accounts, HKD + USD,
  MSFT at two brokers, an AAPL option), FX to USD, 5 hardcoded groups, `/api/v1/portfolio`
  and friends. 10 tests pass.
- ✅ Dashboard UI working in browser mode (KPIs, accounts, allocation tabs, group chips,
  sortable positions table).
- ⚠️ **Rust/Tauri app has never been compiled.** `Cargo.lock` has been resolved and committed. The MSVC C++ Build Tools install requires UAC elevation on Windows (winget exit 1602 when run non-interactively). The user should run the installer with admin approval; then `cargo tauri dev` or `cargo run` can compile the desktop shell.
  Tauri CLI not installed yet (`cargo install tauri-cli --version "^2" --locked`).
- ⏳ Ready to push commits to `origin master`.

### Next steps
1. Install MSVC C++ Build Tools, run Tauri app, verify desktop build.
2. Persist groups/settings (SQLite) + group editing UI.
3. First real broker connector (ask the user which broker first).
4. Bundle the backend as a PyInstaller sidecar so Tauri starts it.
