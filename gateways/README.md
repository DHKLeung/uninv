# Broker Gateways Documentation & Setup Guides

This folder provides step-by-step guides on downloading, installing, and configuring the official standalone broker daemons supported by `uninv`.

---

## Architectural Philosophy: Standalone Broker Daemons

`uninv` does **not** bundle closed-source broker client binaries or proprietary gateway installers directly inside the code repository. Instead:

1. **Broker Daemons Run Standalone on the Host OS:** 
   Official broker gateways—**Trader Workstation (TWS)** from Interactive Brokers and **OpenD** from Futu / Moomoo—are installed and executed directly on your host machine.
2. **Native Authentication & 100% Security:** 
   Running the official broker clients natively allows each broker's native authentication mechanisms—including biometric passkeys (Windows Hello, Apple Touch ID, iPhone Face ID via QR code), FIDO2 hardware USB keys, and SMS/mobile app 2FA—to function seamlessly. `uninv` never prompts for, transmits, or stores your broker passwords or credentials.
3. **Local Socket Communication:** 
   Once logged in, each broker daemon listens on a secure local loopback port on `127.0.0.1` (`7496` for TWS, `11111` for Futu OpenD). The `uninv` Python backend connects locally over standard socket interfaces (`ib_async` for IBKR, `futu-api` for Futubull/Moomoo).
4. **Cross-Platform:** 
   Both TWS and Futu OpenD are officially supported on **Windows, macOS, and Linux**.

---

## Step-by-Step Setup Guides

Before launching `uninv`, set up the broker daemons you use:

| Broker | Supported Client | Default Port | Setup Documentation |
|---|---|---|---|
| **Interactive Brokers (IBKR)** | **Trader Workstation (TWS)** | `7496` | [TWS Setup Guide](tws/instruction.md) |
| **Futu / Moomoo** | **Futu OpenD** | `11111` | [Futu OpenD Setup Guide](futu_gateway/instruction.md) |

*(Note: `uninv` works with either one or both brokers active. If a broker client is offline, `uninv` cleanly marks it as unavailable in Settings while continuing to display live data from any connected broker).*

---

## Why TWS is Enforced over IB Gateway & Client Portal Gateway

* **Client Portal Gateway (`clientportal.gw`) Permanently Abandoned:** IBKR enforced mandatory passkeys on user accounts, but failed to update their legacy Client Portal login page to support WebAuthn / Passkeys, resulting in permanent login lockouts.
* **Trader Workstation (TWS) Enforced over Standalone IB Gateway:** Standalone IB Gateway has recurring WebAuthn/Passkey bugs on Windows when passkeys are stored on mobile devices. In contrast, **Trader Workstation (TWS)** provides a built-in QR code fallback that works seamlessly with mobile Passkeys and Face ID.

For a detailed technical log of all past gateway trials, see [`docs/trials_and_errors.md`](../docs/trials_and_errors.md).
