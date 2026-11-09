# uninv v1.1.0 — Unified Investing Desktop Platform

Welcome to the inaugural release of **uninv** (**uni**fied + **inv**esting)! 

**uninv** is a private, cross-platform desktop application designed for retail investors to unify holdings, multi-currency cash balances, and risk/margin metrics across multiple broker accounts in real time.

---

## 🚀 Key Highlights & What's New in v1.1.0

### 1. Embedded Python Backend Sidecar (Zero Manual Setup)
* **Single-Click Launch:** The Python FastAPI backend is bundled directly inside the desktop installer as an embedded sidecar. When you launch `uninv`, the desktop app boots the backend service in the background, waits for the API to be ready, and connects seamlessly.
* **Clean Process Lifecycle:** When you close the application window, the sidecar backend process is automatically and cleanly terminated.
* **Developer Flexibility:** If you already have the backend running during local development, `uninv` automatically detects the active port (`7541`) and connects without spawning duplicate processes.

### 2. Multi-Broker Ingestion (Interactive Brokers & Futu / Moomoo)
* **Interactive Brokers (TWS & IB Gateway):** Direct socket integration on ports `7496` (TWS) or `4001` (IB Gateway) via native `asyncio` event loop routing on Uvicorn's main thread.
* **Futu Meta-Broker (Futubull & Moomoo):** Traverses all subsidiaries (`FUTUSECURITIES`, `FUTUINC`, `FUTUSG`, `FUTUAU`, `FUTUCA`, `FUTUJP`, `FUTUMY`) across Securities, Futures, and Crypto contexts, automatically consolidating sub-accounts under their Universal Accounts (`uni_card_num`).
* **Zero Credential Risk:** Official broker daemons (IB Gateway and Futu OpenD) run standalone on your machine. Your passwords, biometric passkeys (Windows Hello, Apple Touch ID), hardware FIDO2 keys, and SMS/mobile 2FA are handled directly by official broker software. `uninv` never sees or stores your credentials.

### 3. Consolidated Portfolio & Account Values Board
* **Section 1 — Multi-Account Selector:** Top horizontal bar featuring an **All Accounts** consolidated overview tile (showing total account and position counts plus converted Net Liquidation Value), alongside individual broker account tiles.
* **Section 2 — Account Values Board:** Clean, structured 6-metric financial board:
  * **Row 1:** `Net Liquidation Value`, `Gross Position Value`, and `Cash Balance` (ensuring `Cash Balance + Gross Position Value == Net Liquidation Value`).
  * **Row 2:** `Unrealised P&L` (with colored signed percentage return badge), `Maintenance Margin`, and `Excess Liquidity` cushion.
  * *Note:* When *All Accounts* is selected, account-specific maintenance margin and excess liquidity display an em-dash (`—`), while net liquidation, gross positions, cash, and P&L sum across all accounts.
* **Section 3 — Comprehensive Holdings & Cash Tables:**
  * **Positions Table (13 Columns):** `Broker / Account`, `Instrument / Symbol`, `Type / Exchange`, `Position`, `Avg Price`, `Mark Price`, `Cost Basis`, `Market Value`, `Last Trading Date`, `Days Left`, `Unrealised P&L`, `Weight`, `Currency`.
  * **Days Left Column:** Displays the calendar days remaining until contract expiration for options and futures derivatives (with em-dash `—` for perpetual stocks and crypto). Smart column sorting ranks contracts by expiration while keeping stocks neatly pinned at the bottom.
  * **Multi-Currency Cash Balances Table:** Displays cash balances by individual currency with both raw native balances and live converted amounts matching the Section 2 Cash Balance to the exact penny.

### 4. Live Graph-Routed 11×11 FX Matrix & Instant Currency Switching
* **11 Supported Currencies:** `USD`, `HKD`, `EUR`, `GBP`, `JPY`, `CAD`, `AUD`, `CHF`, `CNH`, `SGD`, `NZD`.
* **Graph-Based Cross-Rate Synthesis:** Direct IDEALPRO market quotes with automatic inversion and cross-rate synthesis via major hubs.
* **Instant In-Memory Switching:** Switching the display currency in the headbar instantly recalculates all portfolio values, market values, and cash balances locally in memory with zero network latency.

### 5. Auto-Refresh & As-Of Precision Tooltip
* **Auto-Refresh Dropdown:** Choose between `Manual`, `1 min`, `2 mins`, `5 mins`, or `10 mins` auto-refresh intervals with built-in overlap prevention.
* **Data Timestamps Tooltip:** Interactive info icon next to the As-Of clock details the exact completion timestamp and latency of each API query (`/api/v1/accounts`, `/api/v1/snapshot`, `/api/v1/fx`).

### 6. Built-in Broker Gateway Manager
* Configure custom gateway host/IP addresses and TCP ports on the fly directly in the **Settings** page.
* Live connection status badges (`✓ Connected` vs `✗ Offline`) test socket connectivity before pulling account data.

---

## 📦 Downloads & Installation Assets

| Platform | Installer File | Description |
|---|---|---|
| **Windows** | `uninv_1.1.0_x64-setup.exe` | Standard Windows NSIS Installer (Includes Start Menu shortcut & uninstaller) |
| **Windows** | `uninv_1.1.0_x64_en-US.msi` | Windows MSI Enterprise Installer |
| **macOS** | `uninv_1.1.0_aarch64.dmg` / `x64.dmg` | macOS Disk Image (Apple Silicon & Intel) |
| **Linux** | `uninv_1.1.0_amd64.deb` | Debian / Ubuntu Package (`sudo apt install ./uninv_1.1.0_amd64.deb`) |
| **Linux** | `uninv_1.1.0_amd64.AppImage` | Portable Linux Executable |

---

## ⚙️ Requirements & Broker Setup

Before launching `uninv`, make sure your broker daemons are running and logged in:
* **Interactive Brokers:** Log into [TWS](https://www.interactivebrokers.com/) (port `7496`) or [IB Gateway](https://www.interactivebrokers.com/) (port `4001`) with API access enabled (`Settings > API > Settings > Enable ActiveX and Socket Clients`).
* **Futu / Moomoo:** Log into [Futu OpenD](https://www.futunn.com/) (port `11111`).
