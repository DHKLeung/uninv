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
- `uninv` targets TWS directly on default port `7496`. FastAPI starts independently of TWS; endpoints return clear diagnostics if TWS is offline and auto-reconnect once TWS is available.

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
- Maintain development runners: `start-all.ps1` / `start-all.cmd` (Windows) and `start-all.sh` (macOS/Linux).
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
- `uninv` connects directly to TWS on port `7496` using `ib_async`. Backend startup is completely decoupled from TWS status.

---

## Trial 8: IBKR Socket API Derivation Quirk — `FuturesOption` & `Option` Multiplier in `averageCost`

### The Problem
When inspecting raw portfolio feeds from IBKR socket updates (`PortfolioItem` in `ib_async` / TWS):
- **For Stocks & Crypto:** `item.averageCost` and `item.marketPrice` are both reported in per-share/unit currency ($115.58 vs $118.95). Multiplier is 1.0.
- **For Futures Options (`FuturesOption`) and Equity Options (`Option`):**
  - `item.marketPrice` is reported as the quoted premium points (e.g., `169.46` index points for an ES option, or `$100.74`/share for a GOOGL option).
  - `item.averageCost` is reported as the **total currency cost for 1 full contract** (e.g., `$4,548.59` for 1 ES option contract = 90.9718 points × 50 multiplier; `$9,665.77` for 1 GOOGL option = $96.6577 × 100 multiplier).

If left unscaled, `average_price` would be in total contract dollars (`$4,548.59`), while `market_price` is in index points (`169.46`), creating a 50x or 100x dimensional scale mismatch! Downstream calculations using `average_price * multiplier` would multiply the contract total by 50 again (yielding -$227,429 instead of -$4,548.59).

### The Solution
We implemented explicit contract type inspection using `isinstance(c, (FuturesOption, Option))` (with `secType in ("OPT", "FOP")` fallback) in `_normalize_average_price()`:
- When dealing with derivative options where `multiplier > 1`:
  $$\text{average\_price} = \frac{\text{averageCost}}{\text{multiplier}}$$
- Both `average_price` and `market_price` are normalized into the exact same quotation units (points or $/share).
- This allows the client application to apply uniform mathematical formulas across every asset class:
  $$\text{cost\_basis} = \text{position} \times \text{average\_price} \times \text{multiplier}$$
  $$\text{market\_value} = \text{position} \times \text{market\_price} \times \text{multiplier}$$
  $$\text{unrealized\_pnl} = (\text{market\_price} - \text{average\_price}) \times \text{position} \times \text{multiplier}$$
- Verified against live account data with exact 0.00 difference against IBKR's internal net liquidation and position values.

---

## Trial 9: FastAPI Threadpool Dispatch vs `ib_async` Stateful TCP Socket (The Silent Event Loop Deadlock)

### The Phenomenon
The desktop app would load smoothly on initial startup, but clicking the "Refresh" button or triggering concurrent requests would intermittently freeze the backend indefinitely. The HTTP request would enter FastAPI's route handler, but `await ib.accountValuesAsync(...)` or `ib.reqTickersAsync(...)` would never return, resulting in a gateway timeout or a permanently hung browser/desktop view.

### The Initial Misconception (The "Python Singleton" Fallacy)
A natural assumption when designing the backend was:
> *"We instantiated `ibkr_service = IBKRService()` as a module-level singleton. It is a single Python object in shared memory. Why can't all FastAPI worker threads simply reuse this connected instance to query TWS?"*

In Python, module-level variables reside in shared heap RAM. Any thread can read the memory address of `ibkr_service` and invoke its methods. However, **an active network connection is not just Python memory: it is an operating system kernel resource bound to an event loop**.

### Technical Root Cause: OS Socket Multiplexing & Event Loop Thread Affinity

1. **How an OS TCP Socket Actually Works:**
   - A TCP socket is represented by an operating system file descriptor / socket handle (`int`).
   - When `ib_async` establishes a connection (`await ib.connectAsync(...)`), it registers that socket handle with the OS kernel multiplexer (`select`/IOCP on Windows, `epoll` on Linux, `kqueue` on macOS) **on the specific `asyncio` event loop running on that specific thread**.
   - The OS kernel will only wake up the thread that executed the kernel polling syscall (`select.select()`, `GetQueuedCompletionStatus()`, or `epoll_wait()`).

2. **FastAPI's Request Dispatching Mechanism:**
   - In FastAPI, route handlers defined with standard `def` (synchronous functions) are treated as blocking I/O:
     ```python
     # ANTI-PATTERN for stateful async socket libraries:
     @router.get("/snapshot")
     def get_snapshot(account_id: str):
         return ibkr_service.get_snapshot(account_id)
     ```
   - FastAPI automatically offloads standard `def` routes to an external threadpool (`anyio.to_thread.run_sync()`, typically with 40 worker threads).
   - Consecutive HTTP requests are arbitrarily assigned to different worker threads: Request 1 $\to$ Thread 1, Request 2 $\to$ Thread 2.

3. **The Step-by-Step Anatomy of the Deadlock:**
   ```
   [FastAPI Threadpool Worker 1]          [FastAPI Threadpool Worker 2]          [TWS (Port 7496)]
                 │                                      │                                │
      Connects & creates socket                         │                                │
      Registers socket on Loop 1                        │                                │
      Loop 1 waits on OS poll (select)                  │                                │
                 │                                      │                                │
                 │                          User clicks "Refresh"                        │
                 │                          Invokes get_snapshot()                       │
                 │                          Runs on Thread 2                             │
                 │                                      │                                │
                 │                          Sends request over shared socket ───────────>│
                 │                          Creates Future on Loop 2                     │
                 │                          Thread 2 blocks waiting for Future           │
                 │                                      │                                │
                 │                          <── TWS sends response packets ──────────────┘
                 │                                      │
   OS delivers packets to Thread 1!                     │
   Loop 1 wakes up and reads data                       │
   Loop 1 has no pending request for this data          │
   Loop 1 tries: future_2.set_result(data)              │
                 │                                      │
                 │                           Thread 2 is STILL sleeping!
                 │                           (set_result alters RAM, but does
                 │                            NOT issue an OS wakeup syscall
                 │                            to Thread 2's kernel poll)
                 │                                      │
                 ▼                                      ▼
            [Confused]                        [DEADLOCK / HANGS FOREVER]
   ```

4. **Why `Future.set_result()` Does Not Wake Up Another Thread's Loop:**
   - An `asyncio.Future` is a plain Python object. Calling `future.set_result(data)` sets `self._result = data` and appends callbacks to a Python list.
   - **Crucially, modifying Python RAM does not issue an OS kernel interrupt.**
   - Thread 2 is suspended inside a blocking OS wait (`select` or Windows completion port). Because Thread 2's kernel polling list has zero registered socket activity, Thread 2's event loop is never woken up by the operating system.
   - Result: Thread 2 hangs indefinitely waiting for an event loop iteration that never executes.

5. **The Cross-Talk / Socket Corruption Hazard:**
   - If Thread 2 writes raw bytes to Thread 1's socket, TWS processes the command and returns packets.
   - Thread 1's socket reader receives packets it never asked for.
   - Thread 1's protocol state machine becomes confused or out-of-sync, while Thread 2 eventually times out with no response.

---

## Trial 10: The Dedicated Background Runner (`_IBRunner`) — And Why It Was Scrapped for Simplicity

### The Initial Fix Attempt
To resolve the threadpool contention, we initially constructed an internal worker runner (`_IBRunner`):
- Spawned a dedicated background daemon thread (`threading.Thread(target=runner_loop, daemon=True)`) hosting a single persistent `asyncio` event loop.
- Added a `threading.Lock` across all operations.
- Marshaled all calls from FastAPI worker threads onto this background loop using `asyncio.run_coroutine_threadsafe(coro, runner_loop).result()`.

### Why It Worked Mechanically
Because all socket creation, reading, writing, and future resolution were restricted exclusively to that single background thread, the cross-thread event loop deadlock was eliminated.

### Why It Was a Code Smell & Anti-Pattern (Fighting the Framework)
Despite functioning, this approach was a textbook case of **patch-on-patch over-engineering**:
1. **Redundant Thread Hopping:** FastAPI and Uvicorn already run on a high-performance, native `asyncio` event loop on the main process thread. Running an async framework to dispatch to a threadpool worker, to acquire a lock, to dispatch to a secondary background thread's async loop, and wait on a threadsafe future was needlessly convoluted.
2. **Maintenance Burden:** Added 280+ lines of threading synchronization, lock management, timeout handlers, and thread lifecycle cleanup code.
3. **Fragile Serialization:** The coarse `threading.Lock` serialized every broker request, preventing concurrent queries (e.g. fetching account values and market tickers simultaneously).

### The Pivot to Simplicity: Pure Native `async def` Routes
Instead of wrapping layers of threads and locks around the problem, we deleted `_IBRunner` entirely and aligned with FastAPI's native design:
- Converted all route handlers in `backend/src/uninv_backend/api/routes.py` to `async def`.
- Converted all service methods in `backend/src/uninv_backend/ibkr.py` and `fx.py` to `async def`.
- **How it works:** When FastAPI encounters an `async def` endpoint, it does NOT offload it to a worker threadpool. Instead, it executes it directly on Uvicorn's main `asyncio` event loop.
- **The Result:** The TCP socket, the route handlers, and the network futures all reside on the exact same loop. Zero thread hops, zero locking primitives, and zero deadlocks. Performance dropped from multi-second lock waits to a crisp **1.4 seconds for a complete portfolio snapshot + 11x11 FX matrix**.

---

## Trial 11: Zero-Cache Architecture & Live Snapshot Integrity

### The Problem with Endpoint Caching
We previously introduced a 15-second in-memory cache (`_cached_matrix`) in `FxRouter` to minimize redundant TWS Forex requests. However, this introduced a direct violation of user intent:
- When a user clicks **"Refresh"**, the explicit expectation is to query the brokers and capture a **100% fresh, live, real-time snapshot** of all positions, prices, and exchange rates.
- Caching caused the UI to display stale exchange rates, created visual discrepancies between raw asset prices and converted totals, and masked recent order executions.

### The Solution
1. **Complete Removal of Caching:** All in-memory snapshot and FX matrix caches were purged from the backend. Every refresh request fetches fresh live market quotes and ledger totals.
2. **Strict Network Timeouts (`asyncio.wait_for`):**
   - Live network queries to brokers can stall if the broker daemon is busy or a specific ticker is illiquid.
   - We wrapped external TWS queries in strict timeouts:
     - **3.0s timeout** for batch Forex tickers (`ib.reqTickersAsync`).
     - **4.0s timeout** for derivative contract qualifications (`ib.qualifyContractsAsync`).
   - If a specific quote or edge fails to resolve within the timeout window, the system falls back gracefully (e.g., computing synthetic cross-rates or returning unpriced positions) rather than hanging the entire application.

---

## Trial 12: Futu OpenD Integration — The `OpenContextBase` Infinite Loop Trap & Fast Socket Probing

### The Problem
When evaluating the official `futu-api` Python client library (v10.12.7208) to connect to Futu OpenD (`127.0.0.1:11111`), inspecting `OpenContextBase.__init__` revealed a critical behavioral trap:
```python
if is_async_connect:
    self._wait_reconnect(0)
else:
    while True:
        self._status = ContextStatus.START
        ret = self._init_connect_sync()
        if ret == RET_OK:
            return
        else:
            if not self._auto_reconnect:
                return
        sleep(self._reconnect_interval) # sleeps 6 seconds and loops forever!
```
When `OpenSecTradeContext(host='127.0.0.1', port=11111)` is initialized while Futu OpenD is offline:
1. `_auto_reconnect` defaults to `True`.
2. The constructor enters an **infinite `while True:` loop**, sleeping 6 seconds between retries.
3. The calling thread is **permanently blocked**, repeatedly logging `WSAECONNREFUSED` with no timeout or exit mechanism.
4. If invoked inside a web server without precautions, this consumes worker threads until the server hangs.

### Additional Challenge: Non-Daemon Background Threads
By default, `futu-api` creates internal background receiver threads for socket processing. If these threads are non-daemon, the Python process refuses to shut down when Uvicorn receives a termination signal (`SIGINT` / `Ctrl+C`).

### The Solution
1. **Pre-Flight TCP Socket Probe (`is_opend_available`):**
   - Before instantiating `OpenSecTradeContext`, `FutuService` executes an instantaneous OS socket probe:
     ```python
     def is_opend_available(self, timeout: float = 0.3) -> bool:
         try:
             with socket.create_connection((self.host, self.port), timeout=timeout):
                 return True
         except OSError:
             return False
     ```
   - If port 11111 is not listening, it immediately aborts in under 0.2 seconds and raises a clean `ConnectionError`:
     `"Cannot connect to Futu OpenD on 127.0.0.1:11111. Please ensure Futu OpenD is running and logged in."`
   - FastAPI catches this and returns a clean `503 Service Unavailable` response to the client immediately without blocking.
2. **Enforce Daemon Threads & Clean Logs:**
   - Configured globally on service import:
     ```python
     futu.SysConfig.set_all_thread_daemon(True)
     futu.SysConfig.enable_console_log(False)
     ```
   - All background threads spawned by Futu exit automatically when the main process terminates.
3. **Threadpool Offloading (`anyio.to_thread.run_sync`):**
   - `futu-api`'s synchronous SDK calls are wrapped in `await anyio.to_thread.run_sync(futu_service.get_snapshot, account_id)`.
   - This executes Futu queries inside FastAPI's external worker threadpool, leaving Uvicorn's main `asyncio` event loop completely free and completely isolated from IBKR's stateful async TCP sockets.
4. **Normalized Derivatives & Multi-Currency Cash:**
   - US and HK option ticker codes (e.g. `US.NVDA250117C00145000`) are parsed using regular expressions into uniform `Position` models with normalized expiration dates (`2025-01-17`), strikes (`145.0`), option types (`CALL`), descriptive instrument names (`NVDA Jan17'25 145 CALL`), and standard 100.0 contract multipliers.
   - Multi-currency balances (`hk_cash`, `us_cash`, `cn_cash`, `jp_cash`, `sg_cash`) are decomposed into typed `CashBalanceItem` lists for multi-currency portfolio aggregation.
