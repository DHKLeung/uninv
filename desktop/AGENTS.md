# AGENTS.md: desktop (Tauri 2 + plain JS)

Rules for `desktop/`. Root `AGENTS.md` applies too. **The user doesn't know Rust**, so explain
any Rust change in plain terms with Python comparisons.

## Layout
- `src/`: the UI, served as-is (Tauri `frontendDist: "../src"`, no `devUrl`, no build step).
  - `index.html`: structured into Global Headbar (as-of tooltip, currency selector, auto-refresh interval dropdown, circular refresh button), Sidebar (Portfolio, Settings, About), and main view containers.
  - `styles.css`: dark theme design system (`:root` variables), hairline borders, stacked cells, and modal/tooltip styles.
  - `assets/`: Purple square app icons (`icon.svg`, `icon.png`, `favicon.png`).
  - `js/api.js`: `apiGet(path)` and `apiPost(path, body)`. Uses Tauri `invoke("api_get")` / `invoke("api_post")` inside the app and falls back to `fetch()` in browser mode.
  - `js/format.js`: money, pct, and quantity formatting (`formatQty` preserves full fractional precision up to 20 decimals), `convertAmount` for FX, and `esc()` for HTML escaping.
  - `js/main.js`: application state manager and DOM renderer:
    - Global state: `brokers`, `accounts`, `snapshots`, `fxMatrix`, `currency`, `selectedTile`, `settings`.
    - Portfolio Page:
      1. **Accounts Selector:** Horizontal tiles ("All Accounts" with account + position count, plus individual accounts).
      2. **Account Values Board:** 6 structured cards across 2 rows. When "All Accounts" is active, Maintenance Margin and Excess Liquidity display `—`, while other metrics aggregate.
      3. **Holdings:**
         - **Positions Table (13 columns):** `Broker / Account`, `Instrument / Symbol`, `Type / Exchange`, `Position`, `Avg Price`, `Mark Price`, `Cost Basis`, `Market Value`, `Last Trading Date`, `Days Left`, `Unrealised P&L`, `Weight`, `Currency`. Rows are never aggregated.
         - **Cash Balances Table (4 columns):** `Broker / Account`, `Currency`, `Amount (RAW)`, `AMOUNT (CONVERTED)`.
    - Settings Page:
      - Broker Gateways section with Host/IP and Port configuration per broker.
      - Edit and Save controls (inputs disabled until Edit is clicked).
      - Live connection testing via `/api/v1/broker-connection-test` with status badges.
    - About Page: displays app icon, `uninv`, `Unified Investing`, description, Version: `1.1.0`, Author: `DHKLeung`.
- `src-tauri/`: Rust shell.
  - `src/lib.rs`: `Backend` state (reqwest client and base URL from `UNINV_BACKEND_URL` / `RwLock`); commands `api_get`, `api_post`, `backend_url`, and `set_backend_url`. Manages sidecar lifecycle with Windows Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`), process tree kill (`taskkill /F /T`), `--parent-pid` argument passing, and exit hooks on `CloseRequested`, `Destroyed`, and `Exit`.
  - `tauri.conf.json`: window config, CSP, bundle, and icons.
  - `icons/`: purple square app icon in `.ico`, `.png`, and multiple resolutions.

## Platforms
- Cross-platform desktop: Windows (WebView2), macOS (WebKit), Linux (WebKitGTK).

## Conventions
- Tauri **2.x** only (`tauri = "2"`).
- No Node.js or bundler. Use vanilla ES modules, no external frameworks, no CDN scripts.
- Escape every API-provided string with `esc()` before inserting into `innerHTML`.
- Number formatting rules:
  - Only monetary / currency values are rounded (to 2 decimal places).
  - Quantities (positions, crypto shares) preserve exact raw float precision.
  - Average Price and Mark Price remain in raw trading currency.
  - Cost Basis, Market Value, and Unrealised P&L convert dynamically via the FX matrix.
- Add a Rust `#[tauri::command]` only for native features. Generic API communication uses `api_get` and `api_post`.
