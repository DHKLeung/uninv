# Broker Gateways Documentation

This folder documents the external broker gateways supported by `uninv`.

## Architectural Philosophy

`uninv` does **not** bundle closed-source broker client binaries or proprietary gateway installers directly inside the code repository. Instead:

1. **Broker Daemons Run Standalone:** Official broker gateways (such as **IB Gateway** from Interactive Brokers and **OpenD** from Futu) are installed and executed natively on your host machine.
2. **Native Authentication:** This allows each broker's native security features—including biometric passkeys (Windows Hello / Apple Touch ID), FIDO2 hardware keys, and SMS/mobile 2FA—to function seamlessly without reverse-engineering.
   > **Note on IBKR Client Portal Gateway:** We deliberately abandoned the legacy Client Portal Web API gateway (`clientportal.gw`). IBKR enforced mandatory passkey authentication on user accounts, but neglected to update their legacy Client Portal login page to support WebAuthn / Passkeys, making login impossible. Standalone IB Gateway solves this completely.
3. **Local Socket Communication:** Once logged in, the gateway listens on a secure local loopback port (`127.0.0.1`). The `uninv` Python backend connects via standard asynchronous client libraries (`ib_async` for IBKR, `futu-api` for Futubull).
4. **Cross-Platform:** Because both IB Gateway and Futu OpenD are officially supported on **Windows, macOS, and Linux**, `uninv` remains fully cross-platform.

## Supported Gateways

- [`ib_gateway/instruction.md`](ib_gateway/instruction.md): Interactive Brokers Gateway & TWS setup guide.
- `futu_gateway/`: Futu OpenD setup guide (upcoming).
