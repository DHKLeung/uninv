"""Quick verification script for IB Gateway / TWS using ib_async."""

import asyncio
from ib_async import IB


async def test_connection():
    ib = IB()

    # Ports: 7496 (TWS Live), 4001 (IB Gateway Live), 7497 (TWS Paper), 4002 (IB Gateway Paper)
    ports = [7496, 4001, 7497, 4002]
    connected = False
    connected_port = None

    for port in ports:
        try:
            print(f"Probing 127.0.0.1:{port}...")
            await ib.connectAsync("127.0.0.1", port, clientId=99, timeout=3.0)
            print(f"  --> Successfully connected to port {port}!")
            connected = True
            connected_port = port
            break
        except Exception:
            pass

    if not connected:
        print("\nCould not connect to IB Gateway / TWS on ports 7496, 4001, 7497, or 4002.")
        print("Please check that TWS / IB Gateway is running with Socket API enabled.")
        return

    accounts = ib.managedAccounts()
    print(f"\n[OK] Managed Accounts: {accounts}")

    for acct in accounts:
        print(f"\n{'='*60}\nAccount: {acct}\n{'='*60}")

        # Account balances
        values = ib.accountValues(account=acct)
        key_tags = {
            "NetLiquidationByCurrency": "Net Liquidation",
            "TotalCashBalance": "Total Cash Balance",
            "GrossPositionValue": "Gross Position Value",
            "UnrealizedPnL": "Unrealized P&L",
            "RealizedPnL": "Realized P&L",
            "BuyingPower": "Buying Power",
        }
        print("\n--- Key Balances ---")
        for v in values:
            if v.tag in key_tags and v.currency in ("USD", "HKD", "BASE"):
                label = key_tags[v.tag]
                try:
                    val_float = float(v.value)
                    print(f"  {label:<24} ({v.currency}): {val_float:>14,.2f}")
                except ValueError:
                    print(f"  {label:<24} ({v.currency}): {v.value:>14}")

        # Positions
        positions = await ib.reqPositionsAsync()
        acct_positions = [p for p in positions if p.account == acct]
        print(f"\n--- Open Positions ({len(acct_positions)}) ---")
        for p in acct_positions:
            c = p.contract
            sym = c.localSymbol or c.symbol
            sec = c.secType
            curr = c.currency
            expiry = getattr(c, "lastTradeDateOrContractMonth", "") or ""
            print(f"  {sym:<16} {sec:<6} Qty: {p.position:>10.4f}  AvgCost: {p.avgCost:>10.2f} {curr} {expiry}")

    ib.disconnect()
    print(f"\n[Done] Successfully verified connection via port {connected_port}.")


if __name__ == "__main__":
    asyncio.run(test_connection())
