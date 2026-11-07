# Engineering Trials, Errors & Architectural Decisions Log

This document records the technical trials, dead ends, and architectural pivots encountered while building `uninv`. It serves as a persistent record of **what was tried, why it failed, and what was chosen instead**.

---

## Trial 1: Interactive Brokers Client Portal Gateway (`clientportal.gw`)

### The Hypothesis
Use IBKR's official **Client Portal Web API Gateway** (a local Java-based Vert.x proxy) to expose RESTful HTTP/JSON endpoints (`/portfolio/accounts`, `/positions/0`, `/ledger`) on `https://localhost:5000`. This seemed attractive because our backend is Python FastAPI, making standard HTTP calls via `httpx` straightforward.

### What Was Built
1. Downloaded the official `clientportal.gw.zip` (~10.5 MB) from IBKR.
2. Configured `root/conf.yaml` for local SSL on port 5000 with CORS enabled.
3. Created launcher scripts (`run-ibkr-gateway.ps1`, `run.bat`, `run.sh`) with automated OpenJDK 21 path resolution.
4. Tested local Vert.x boot, which loaded successfully and listened on port 5000.

### Why It Failed (The Showstoppers)

1. **Mandatory Passkey / WebAuthn Authentication Blocker:**
   - **The Problem:** Interactive Brokers recently enforced mandatory biometric passkeys (FIDO2 / WebAuthn) for user accounts.
   - **The Failure:** The Client Portal Gateway's local login page (`https://localhost:5000`) is legacy and has not been updated by IBKR to support browser WebAuthn / Passkey APIs.
   - **The Result:** When attempting to log in, the browser never triggers the Windows Hello / Touch ID / security key prompt. The login fails with no alternative fallback, **permanently locking out passkey-secured users**.
2. **Brittle Session Lifecycle & Daily Dropouts:**
   - The gateway requires manual daily browser logins and frequent `/tickle` heartbeat calls. If a connection drops, the app cannot self-heal without forcing the user back into a web browser.
3. **Self-Signed TLS Certificate Complications:**
   - Ships with an internal self-signed certificate (`vertx.jks`), requiring browsers to bypass security warnings and HTTP clients (`httpx`/`requests`) to disable SSL verification (`verify=False`).
4. **Aggressive Backend Server-Side Caching:**
   - Portfolio positions and ledger updates are aggressively cached on IBKR's edge servers, requiring explicit cache-invalidation API calls before fetching fresh data.

### Decision
**Completely abandoned Client Portal Gateway.** All 43+ JARs, scripts, and gateway files were purged from the repository to prevent repository bloat and technical debt.

---

## Trial 2: Bundling Gateway Binaries in the Git Repository

### The Hypothesis
Place the broker gateway executables and JAR files inside the repository (under `gateways/ibkr-gateway/` and `gateways/futubull-gateway/`) so developers can run everything with zero external downloads.

### Why It Failed / Was Suboptimal

1. **Repository Bloat:**
   - The Java Client Portal gateway alone added ~12 MB of JAR files.
   - Futubull's **Futu OpenD** is an executable daemon that weighs 50 MB to 100 MB *per operating system* (Windows `.exe`, macOS `.dmg`, Linux `.tar.gz`). Storing these in Git would quickly bloat repo size beyond hundreds of megabytes.
2. **Git Tracking Quirk:**
   - Standard Python `.gitignore` rules ignore `build/` and `dist/`. The gateway package contained internal `build/lib/runtime/*.jar` and `dist/*.jar` directories, causing git to silently drop critical dependencies unless gitignore rules were carefully customized.
3. **Security & Sandboxing:**
   - Gateways store authentication tokens, session cookies, and runtime logs (`logs/`, `.vertx/`). Keeping them in the repo creates risk of committing transient logs or session state.

### Decision
**Adopted the "Standalone Host Daemon" Pattern:**
- Broker gateways (IB Gateway and Futu OpenD) are **external standalone programs** installed on the host OS.
- The repository only tracks lightweight setup guides, connection parameters, and automated probe scripts (`gateways/ib_gateway/instruction.md`, `gateways/README.md`).
- Gateways run independently and expose localhost loopback TCP sockets (`127.0.0.1`).

---

## Trial 3: Trader Workstation (TWS) vs IB Gateway

### The Trade-off
We needed a socket server for the IBKR API. We compared the two official IBKR desktop applications:

| Metric | Trader Workstation (TWS) | IB Gateway (Chosen) |
| :--- | :--- | :--- |
| **Memory Footprint** | 1.5 GB – 2.5 GB RAM | 150 MB – 250 MB RAM |
| **CPU Usage** | High (rendering live charts, tick ladders, news) | Negligible (headless background socket server) |
| **Startup Time** | 30–60 seconds | 5–10 seconds |
| **Passkey Support** | Native (desktop login dialog) | Native (desktop login dialog) |
| **Cross-Platform** | Windows, macOS, Linux | Windows, macOS, Linux |
| **API Protocol** | Identical IB Socket Protocol | Identical IB Socket Protocol |
| **Default Live Port** | `7496` (Paper: `7497`) | `4001` (Paper: `4002`) |

### Decision
**Primary target: Standalone IB Gateway.**
- Provides the lowest resource overhead and runs quietly in the background without UI clutter.
- Because both speak the identical socket protocol, `uninv` automatically probes both port ranges (`4001`/`4002` for Gateway, `7496`/`7497` for TWS), allowing users to use whichever they prefer.

---

## Trial 4: Python Socket Client — Official `ibapi` vs `ib_async`

### The Trade-off
To talk to the IB socket server from Python, we evaluated the official package vs the modern community standard:

1. **Official `ibapi` (Interactive Brokers):**
   - **Architecture:** Direct mechanical translation of C++ code into Python.
   - **Pattern:** Callback-driven with `EClient` and `EWrapper`. Requires a separate background thread running `app.run()`.
   - **FastAPI Integration:** Poor. Bridging callbacks and background threads into FastAPI's native `asyncio` event loop requires writing 50+ lines of custom locks, queues, and futures per API route.
   - **Code Quality:** Highly imperative and un-Pythonic.
2. **`ib_async` (Modern Async Community Standard, successor to `ib_insync`):**
   - **Architecture:** Pure Python asyncio socket implementation.
   - **Pattern:** Native `async/await` coroutines (`await ib.connectAsync(...)`, `await ib.accountValuesAsync(...)`).
   - **FastAPI Integration:** 100% native. Routes can await responses directly with no thread bridging.
   - **State Sync:** Automatically maintains live in-memory state of positions and account values.
   - **Community:** The de facto standard across algorithmic trading and financial engineering.

### Decision
**Adopted `ib_async` (v2.1.0+).** It enables clean, robust, non-blocking FastAPI endpoints that map directly to our Pydantic models.

---

## Trial 5: Platform Scope (Cross-Platform vs Windows-Only)

### The Exploration
When the Client Portal Gateway failed, we briefly considered narrowing the scope to Windows-only under the assumption that TWS/Gateway passkeys might require Windows-specific APIs.

### The Realization
- **IB Gateway** is officially released for **Windows, macOS (Apple Silicon + Intel), and Linux (Ubuntu)**.
- **Futu OpenD** is officially released for **Windows, macOS, and Linux**.
- Both daemons expose standard **local TCP loopback sockets** (`127.0.0.1`), which Python interacts with identically across all operating systems.
- Tauri 2 and FastAPI are already fully cross-platform.

### Decision
**Preserve Cross-Platform Support (Windows, macOS, Linux):**
- Maintain CI workflows on `windows-latest`, `macos-latest`, and `ubuntu-latest`.
- Maintain development runners: `dev.ps1` / `dev.cmd` (Windows) and `dev.sh` (macOS/Linux).
- Document OS-specific gateway setup instructions under `gateways/`.

---

## Trial 6: The "Insert a Security Key (USB)" Blocker on Windows 10 with iPhone Passkeys

### The Problem
When logging into standalone **IB Gateway** on Windows, entering credentials triggers a Passkey challenge. The native **Windows Security** modal appears, but strictly displays:
> *"Making sure it's you: Insert your security key into the USB port."*

The user's IBKR passkey is stored on their **iPhone (iCloud Keychain)**, not on a physical USB hardware token (YubiKey). There is no apparent way to tap the phone, causing an apparent dead end.

### Technical Root Cause Discovered
1. **Windows 10 vs Windows 11 WebAuthn Discrepancy:**
   - The user is on **Microsoft Windows 10 Home (Build 19045)**.
   - Cross-device passkey authentication (using Bluetooth / QR code handoff to an iPhone/Android device via FIDO caBLE) was **only introduced in Windows 11**.
   - In Windows 10, the OS-level WebAuthn subsystem (`webauthn.dll`) only supports two authenticators:
     1. Local **Windows Hello** (PIN / Biometrics on this device).
     2. Physical **USB/NFC FIDO2 hardware tokens** (YubiKeys).
   - Because Windows 10 has no native cross-device iOS handoff in desktop apps, it defaults to demanding a physical USB security key.
2. **Embedded JxBrowser Limitations:**
   - IB Gateway renders its login flow using JxBrowser. Unlike Google Chrome (which implements its own proprietary WebAuthn Bluetooth relay to iPhones), desktop Java/CEF embedded browsers delegate directly to the underlying Windows OS WebAuthn dialog.

### The Enforced Security Model (No Legacy 2FA Fallback)
Important fact: Once a passkey is registered on an IBKR account, **IBKR strictly enforces Passkeys only**. Legacy 2FA methods (SMS, push notification IB Key, and Challenge-Response) are disabled by IBKR's security policy.

---

## Trial 7: The TWS Breakthrough — "Cancel USB & Scan QR Code" Workflow

### The Discovery
When logging into **Trader Workstation (TWS)** on Windows 10, entering credentials initially triggers the exact same Windows Security prompt:
> *"Making sure it's you: Insert your security key into the USB port."*

However, the behavioral difference between IB Gateway and TWS when dismissed is crucial:

| Action on "Insert USB key" prompt | IB Gateway | Trader Workstation (TWS) |
| :--- | :--- | :--- |
| **Clicking "Cancel"** | Aborts login entirely with no alternatives. | **Catches cancellation and reveals "Use QR code for iPhone"!** |
| **iPhone Passkey Support** | Broken (trapped in USB prompt). | **Fully working via on-screen QR code scan.** |

### The Working Authentication Sequence in TWS
1. Launch TWS and enter username and password.
2. When Windows Security pops up asking to *"Insert a security key (USB)"*, click **Cancel**.
3. TWS immediately reveals its fallback options: click **"Use QR code for iPhone"**.
4. A dynamic QR code appears directly on your PC monitor.
5. Point your iPhone camera at the QR code, tap the prompt, and approve with **Face ID**.
6. **TWS logs in immediately!**

### Architectural Takeaway
For passkey-enforced IBKR accounts on Windows 10 where the passkey resides in iOS iCloud Keychain:
- **Trader Workstation (TWS)** is the winning client because of its built-in QR code fallback handler.
- Once logged in, TWS exposes the exact same socket API as IB Gateway (listening on port `7496` for Live, `7497` for Paper).
- `uninv` automatically detects port `7496`/`7497` and connects using `ib_async`.
