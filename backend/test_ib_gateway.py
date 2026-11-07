"""Quick verification script for IB Gateway / TWS using ib_async."""

import asyncio
from ib_async import IB


async def test_connection():
    ib = IB()

    # Try standard ports:
    # 4001: IB Gateway Live
    # 4002: IB Gateway Paper
    # 7496: TWS Live
    # 7497: TWS Paper
    ports = [4001, 4002, 7496, 7497]
    connected = False
    connected_port = None

    for port in ports:
        try:
            print(f"Probing 127.0.0.1:{port}...")
            await ib.connectAsync("127.0.0.1", port, clientId=1, timeout=3.0)
            print(f"  --> Successfully connected to port {port}!")
            connected = True
            connected_port = port
            break
        except Exception:
            pass

    if not connected:
        print("\nCould not connect to IB Gateway / TWS on ports 4001, 4002, 7496, or 7497.")
        print("Please check:")
        print("  1. Is IB Gateway running and logged in?")
        print("  2. In Configure -> Settings -> API -> Settings, is 'Enable ActiveX and Socket Clients' checked?")
        return

    accounts = ib.managedAccounts()
    print(f"\n[OK] Managed Accounts: {accounts}")

    for acct in accounts:
        print(f"\n{'='*55}\nAccount: {acct}\n{'='*55}")

        # Request account summary values
        values = await ib.accountValuesAsync(acct)
        print("\n--- Balances ---")
        for v in values:
            if v.tag in ("NetLiquidationByCurrency", "TotalCashBalance", "UnrealizedPnL", "RealizedPnL") and v.currency in ("USD", "HKD", "BASE"):
                print(f"  {v.tag:<28} ({v.currency}): {float(v.value):>14,.2f}")

        # Request positions
        positions = [p for p in ib.positions() if p.account == acct]
        print(f"\n--- Positions ({len(positions)}) ---")
        for p in positions:
            sym = p.contract.localSymbol or p.contract.symbol
            sec = p.contract.secType
            curr = p.contract.currency
            print(f"  {sym:<20} {sec:<6} Qty: {p.position:>8}  AvgCost: {p.avgCost:>10.2f} {curr}")

    ib.disconnect()
    print(f"\n[Done] Successfully verified connection via port {connected_port}.")


if __name__ == "__main__":
    asyncio.run(test_connection())
