# Interactive Brokers Gateway (IB Gateway) Setup Guide

This guide explains how to install, configure, and connect **IB Gateway** (or **Trader Workstation / TWS**) to `uninv` using `ib_async`.

---

## 1. Overview & Architecture

Instead of bundling heavy third-party broker binaries or using the legacy Client Portal gateway (which cannot handle modern WebAuthn/Passkey authentication), `uninv` interfaces with **standalone broker daemons** running on your local machine:

```
┌────────────────────────────────────────┐
│ Standalone Broker Gateway (User-run)   │
│ - IB Gateway / TWS (Ports 4001 / 7496) │ ──(Passkey / 2FA / Login GUI)
│ - Futu OpenD       (Port 11111)        │
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

### Why IB Gateway over TWS?
- **Lightweight:** IB Gateway contains the exact same communication engine as Trader Workstation (TWS) without the heavy charting, newsfeeds, and GUI components. It uses a fraction of the RAM and CPU.
- **Passkey Support:** Natively supports biometric/FIDO2 passkeys, Windows Hello, Touch ID (macOS), and IBKR Mobile Key.
- **Cross-Platform:** Available on **Windows**, **macOS**, and **Linux**.

*(Note: If you already have full TWS installed and running, `uninv` can connect to TWS just as easily by pointing to port 7496/7497).*

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
