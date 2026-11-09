# Interactive Brokers Trader Workstation (TWS) Setup Guide

This guide explains how to install, configure, and connect **Trader Workstation (TWS)** to `uninv` using `ib_async`.

---

## 1. Overview & Architecture

### Why TWS is Enforced (Passkey & Authentication Stability)
`uninv` exclusively uses **Trader Workstation (TWS)** as the official gateway for Interactive Brokers:
* **Flawless Passkey / WebAuthn Support:** IBKR enforces mandatory biometric passkeys (FIDO2 / WebAuthn) on user accounts. When logging in, TWS supports Windows Hello, security keys, and built-in QR code authentication for mobile devices (iPhone Face ID / Android). Standalone IB Gateway and the deprecated Client Portal Gateway suffer from WebAuthn bugs on Windows that can lock users out.
* **Rock-Solid Local Socket API:** Once logged in, TWS exposes a fast, stateful local TCP socket on port `7496`. The `uninv` Python backend connects asynchronously using `ib_async` directly on Uvicorn's main event loop.
* **Independent Startup:** FastAPI starts up independently whether TWS is running or not. If TWS is offline, `uninv` displays a clear connection status badge and auto-connects the moment you launch TWS.

```
┌────────────────────────────────────────┐
│ Standalone Broker Gateway (User-run)   │
│ - TWS (Port 7496)                      │ ──(Passkey / Face ID / 2FA Login)
│ - Futu OpenD (Port 11111)              │
└──────────────────┬─────────────────────┘
                   │ Local TCP Socket
┌──────────────────▼─────────────────────┐
│ uninv Python Backend (ib_async)        │
│ FastAPI on http://127.0.0.1:7541       │
└──────────────────┬─────────────────────┘
                   │
┌──────────────────▼─────────────────────┐
│ uninv Desktop App (Tauri 2)            │
└────────────────────────────────────────┘
```

---

## 2. Installation Links

Download the official standalone **Trader Workstation (TWS)** installer for your operating system:

| Platform | Download Link | Notes |
| :--- | :--- | :--- |
| **Windows** | [TWS for Windows (64-bit)](https://www.interactivebrokers.com/en/trading/tws.php) | Standard `.exe` installer |
| **macOS** | [TWS for macOS](https://www.interactivebrokers.com/en/trading/tws.php) | Apple Silicon & Intel `.dmg` |
| **Linux** | [TWS for Linux (64-bit)](https://www.interactivebrokers.com/en/trading/tws.php) | `.sh` standalone installer |

---

## 3. Configuration Step-by-Step

After installing and logging into TWS:

1. Open **File** &rarr; **Global Configuration** &rarr; **API** &rarr; **Settings**.
2. Check **"Enable ActiveX and Socket Clients"**.
3. Set / Verify the **Socket port**:
   - **TWS Live:** `7496` *(Default)*
   - **TWS Paper:** `7497` *(Default)*
4. Ensure **"Allow connections from localhost only"** is checked (recommended for security).
5. Ensure **"Read-Only API"**:
   - Checked if you only want `uninv` to view accounts and positions.
   - Unchecked if you plan to execute rebalancing orders or option trades later.
6. Under **Trusted IPs**, add `127.0.0.1` if prompted.
7. Click **Apply** &rarr; **OK**.

---

## 4. Daily Workflow

1. **Start TWS** on your machine and log in with your credentials and passkey.
2. Launch `uninv`:
   - Windows: Run `.\scripts\start-all.ps1` (or double-click `scripts\start-all.cmd`).
   - macOS / Linux: Run `./scripts/start-all.sh`.
3. The Python backend automatically detects the active socket on port `7496` and streams live positions, margin metrics, and account balances into your dashboard.

---

## 5. Python Verification Script

To quickly test your local TWS connection outside the app, run from `backend/`:

```powershell
uv run python -c "
import asyncio
from ib_async import IB

async def main():
    ib = IB()
    port = 7496
    print(f'Connecting to TWS on 127.0.0.1:{port}...')
    try:
        await ib.connectAsync('127.0.0.1', port, clientId=999, timeout=3.0, readonly=True)
        print('Connected successfully to TWS!')
        print('Managed Accounts:', ib.managedAccounts())
        ib.disconnect()
    except Exception as e:
        print('Connection failed:', e)

asyncio.run(main())
"
```

---

## 6. Troubleshooting

- **`Connection refused` / `Timeout`:**
  - Verify TWS is running and logged in.
  - Verify the port: TWS defaults to `7496` (Live) / `7497` (Paper).
  - Ensure **"Enable ActiveX and Socket Clients"** is checked in TWS API Settings.
- **Port collision:**
  - Ensure no other application is using port `7496`.
  - In `uninv`'s **Settings** page, you can update the configured TWS port if running paper trading (`7497`) or a custom port.
- **Auto-restart:**
  - You can configure TWS's auto-restart time under **File** &rarr; **Global Configuration** &rarr; **Lock and Exit**.
