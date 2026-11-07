# Interactive Brokers Gateway (IB Gateway) Setup Guide

This guide explains how to install, configure, and connect **IB Gateway** (or **Trader Workstation / TWS**) to `uninv` using `ib_async`.

---

## 1. Overview & Architecture

### Why Client Portal Gateway Was Abandoned (The Mandatory Passkey Blocker)
Initially, using Interactive Brokers' **Client Portal Gateway** (`clientportal.gw` / CP Web API) seemed appealing for a REST/JSON interface. However, **it is completely broken for accounts with mandatory Passkeys**:
- **No WebAuthn / Passkey Support:** IBKR recently began enforcing mandatory biometric passkeys (FIDO2 / WebAuthn) for user accounts. However, IBKR's Client Portal Gateway web interface (`https://localhost:5000`) is legacy and has not been updated to support WebAuthn APIs. When attempting to log in, it completely fails to trigger the browser's passkey authentication prompt.
- **Permanent Lockout:** Because IBKR enforces passkeys and the gateway cannot prompt for them, users with passkey-secured accounts are completely locked out of authenticating through the Client Portal Gateway.
- **Instability & Daily Dropouts:** In addition to the passkey blocker, the Client Portal gateway suffers from aggressive session timeouts (requiring daily re-logins through a browser), self-signed TLS certificate complications, and aggressive backend caching.

For these reasons, **Client Portal Gateway was permanently abandoned**.

---

### The Solution: Standalone IB Gateway / TWS

`uninv` interfaces directly with **standalone broker daemons** running on your local machine:

```
┌────────────────────────────────────────┐
│ Standalone Broker Gateway (User-run)   │
│ - TWS (Port 7496)                      │ ──(Passkey / 2FA / Login GUI)
│ - Futu OpenD (Port 11111)              │
└──────────────────┬─────────────────────┘
                   │ Local TCP Socket
┌──────────────────▼─────────────────────┐
│ uninv Python Backend (ib_async)        │
│ FastAPI on http://127.0.0.1:8000       │
└──────────────────┬─────────────────────┘
                   │
┌──────────────────▼─────────────────────┐
│ uninv Desktop App (Tauri 2)            │
└────────────────────────────────────────┘
```

### Why IB Gateway vs TWS?
- **IB Gateway:** Contains the exact same communication engine as TWS without the heavy charting, newsfeeds, and GUI components. Uses ~150 MB RAM (vs ~2 GB for TWS). Ideal for headless or low-resource use.
- **Trader Workstation (TWS):** Recommended on Windows 10 if your passkey is on an iPhone. When TWS prompts for a USB security key, clicking **Cancel** reveals the built-in **"Use QR code for iPhone"** fallback, allowing seamless login via Face ID.
- **Direct TWS Socket API:** `uninv` connects directly to TWS on port `7496`. FastAPI starts up independently whether TWS is running or not; when an endpoint is called while TWS is offline, it provides clear connection instructions and auto-reconnects as soon as TWS is launched.

---

## 2. Installation Links

Download the official standalone IB Gateway installer for your operating system:

| Platform | Download Link | Notes |
| :--- | :--- | :--- |
| **Windows** | [IB Gateway for Windows (64-bit)](https://www.interactivebrokers.com/en/trading/ib-gateway.php) | Standard `.exe` installer |
| **macOS** | [IB Gateway for macOS](https://www.interactivebrokers.com/en/trading/ib-gateway.php) | Apple Silicon & Intel `.dmg` |
| **Linux** | [IB Gateway for Linux (64-bit)](https://www.interactivebrokers.com/en/trading/ib-gateway.php) | `.sh` standalone installer |

---

## 3. Configuration Step-by-Step

After installing and logging into IB Gateway:

1. Open **Configure** &rarr; **Settings** &rarr; **API** &rarr; **Settings**.
   *(In TWS: **File** &rarr; **Global Configuration** &rarr; **API** &rarr; **Settings**)*.
2. Check **"Enable ActiveX and Socket Clients"**.
3. Set / Verify the **Socket port**:
   - **IB Gateway Live:** `4001` *(Default)*
   - **IB Gateway Paper:** `4002` *(Default)*
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

1. **Start IB Gateway** (or TWS) on your machine and log in with your credentials and passkey.
2. Launch `uninv`:
   - Windows: Run `.\scripts\dev.ps1` (or double-click `dev.cmd`).
   - macOS / Linux: Run `./scripts/dev.sh`.
3. The Python backend automatically detects the active socket and streams live positions and account balances into your dashboard.

---

## 5. Python Verification Script

To quickly test your local IB Gateway connection outside the app, run from `backend/`:

```powershell
uv run python -c "
import asyncio
from ib_async import IB

async def main():
    ib = IB()
    # 4001 for IB Gateway Live, 4002 for Paper (or 7496/7497 for TWS)
    port = 4001
    print(f'Connecting to IB Gateway on 127.0.0.1:{port}...')
    await ib.connectAsync('127.0.0.1', port, clientId=1)
    print('Connected successfully!')
    print('Managed Accounts:', ib.managedAccounts())
    for pos in ib.positions():
        print(f'  {pos.contract.symbol} ({pos.contract.secType}): {pos.position} @ {pos.avgCost}')
    ib.disconnect()

asyncio.run(main())
"
```

---

## 6. Troubleshooting

- **Connection Refused (`Errno 111` or `WinError 10061`):**
  - Verify IB Gateway is running and logged in.
  - Check that **"Enable ActiveX and Socket Clients"** is checked in API Settings.
  - Verify the port: IB Gateway defaults to `4001` (Live) / `4002` (Paper), while TWS defaults to `7496` (Live) / `7497` (Paper).
- **Socket Disconnects Overnight:**
  - IBKR performs daily server resets (typically 23:45–00:45 local exchange time).
  - You can configure IB Gateway's auto-restart time under **Configure** &rarr; **Settings** &rarr; **Lock and Exit**.
