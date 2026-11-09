# Futu OpenD Setup Guide

This guide explains how to install, configure, and connect **Futu OpenD** (富途开放API网关) to `uninv` using `futu-api`.

---

## 1. Overview & Architecture

`uninv` interfaces with Futubull / Moomoo through **Futu OpenD**, the official standalone daemon provided by Futu:

```
┌────────────────────────────────────────┐
│ Futu OpenD (Standalone Daemon)         │
│ - GUI or CLI version                   │ ──(Futubull / Moomoo 2FA / Login)
│ - Listens on 127.0.0.1:11111           │
└──────────────────┬─────────────────────┘
                   │ Local TCP Socket
┌──────────────────▼─────────────────────┐
│ uninv Python Backend (futu-api)        │
│ FastAPI on http://127.0.0.1:7541       │
└──────────────────┬─────────────────────┘
                   │
┌──────────────────▼─────────────────────┐
│ uninv Desktop App (Tauri 2)            │
└────────────────────────────────────────┘
```

### Why Standalone Futu OpenD?
1. **Separation of Concerns:** The standard Futubull desktop app is built for manual trading and does not expose a public socket API. Futu provides OpenD as a dedicated, lightweight gateway program.
2. **Native Authentication & 2FA:** OpenD handles password login, device verification, and 2FA tokens directly through Futu's authentication servers. Once logged in, it maintains the session.
3. **Local Loopback Communication:** OpenD exposes an encrypted or plain local TCP socket on port `11111`. `uninv` talks to it locally over loopback (`127.0.0.1`), ensuring zero credentials or keys are hardcoded in the codebase.
4. **Cross-Platform:** OpenD is officially available for **Windows, macOS, and Linux (CentOS/Ubuntu)**.

---

## 2. Installation & Download Links

Download the official standalone Futu OpenD package for your operating system:

| Platform | Recommended Version | Download Page | Notes |
| :--- | :--- | :--- | :--- |
| **Windows** | **FutuOpenD GUI (Visualization)** | [Futu Open API Downloads](https://openapi.futunn.com/) or [Futu API Portal](https://futuapi.com/) | Includes visual login dialog and status monitor |
| **macOS** | **FutuOpenD for macOS** | [Futu Open API Downloads](https://openapi.futunn.com/) | Intel & Apple Silicon support |
| **Linux** | **FutuOpenD for CentOS/Ubuntu** | [Futu Open API Downloads](https://openapi.futunn.com/) | Headless CLI / daemon mode |

---

## 3. Configuration Step-by-Step

### Step 1: Launch Futu OpenD
* On Windows, extract the downloaded zip file and double-click `FutuOpenD.exe` (or launch the GUI version).
* A login window will appear.

### Step 2: Log into Your Account
* Enter your **Futu ID / Moomoo ID** (or registered phone/email) and password.
* Complete any 2FA verification challenge (SMS code or mobile app push approval).
* Once authenticated, OpenD's status indicators will turn green.

### Step 3: Verify Connection Settings
In OpenD's settings panel (right sidebar in GUI, or `FutuOpenD.xml` in CLI):
* **Listening IP:** `127.0.0.1` (or `0.0.0.0`)
* **API Port:** `11111` (default)
* **Log Level:** `info`

### Step 4: Verify Socket Listener in PowerShell
To confirm OpenD is actively listening on port 11111:

```powershell
Get-NetTCPConnection -LocalPort 11111 -State Listen -ErrorAction SilentlyContinue
```

If it returns an active listener on `127.0.0.1:11111`, OpenD is ready!

---

## 4. How `uninv` Connects

* **API Endpoints:**
  * `GET /api/v1/supporting-brokers`: Returns `[{"id": "ibkr", "name": "Interactive Brokers"}, {"id": "futu", "name": "Futu"}]`.
  * `GET /api/v1/accounts?broker_id=futu`: Queries OpenD and returns your managed account IDs.
  * `GET /api/v1/snapshot?broker_id=futu&account_id={id}`: Pulls live account margins, cash balances, and positions.
  * `GET /api/v1/broker-connection-test?broker_id=futu`: Tests if Futu OpenD is reachable on the configured host/port.
  * `GET` / `POST /api/v1/broker-gateway-config`: Reads or updates the configured host/port for Futu OpenD.
* **Fast Offline Detection:** `uninv` automatically probes port 11111 with a fast 0.2s socket check before making requests. If OpenD is offline, the backend returns an immediate HTTP 503 error with troubleshooting instructions, rather than hanging.
* **Non-Blocking Architecture:** `futu-api`'s synchronous SDK calls are executed inside FastAPI's worker threadpool via `anyio.to_thread.run_sync()`, leaving Uvicorn's main `asyncio` event loop completely unblocked.
