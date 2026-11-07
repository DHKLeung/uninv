"""Interactive Brokers connector service using ib_async."""

import contextlib
import logging
import threading

from ib_async import IB, Contract, FuturesOption, Option

from uninv_backend.config import get_settings
from uninv_backend.models import AccountValues, CashBalanceItem, Position

logger = logging.getLogger(__name__)


def _normalize_average_price(
    average_cost: float,
    contract: Contract,
    multiplier: float,
) -> float:
    """Normalize raw IBKR average cost to a unit quote price.

    Interactive Brokers API Quirk:
    - For Stocks, Crypto, and Bonds:
      `item.averageCost` represents the unit price paid per share/coin.
      `item.marketPrice` is also quoted per share/coin.
      Multiplier is 1.0.

    - For Futures Options (`FuturesOption`, `secType='FOP'`)
      and Equity Options (`Option`, `secType='OPT'`):
      `item.marketPrice` is quoted in premium points (e.g. 169.46 points for ES options,
      or $100.74/share for GOOGL options).
      However, `item.averageCost` in IBKR's socket feed represents the TOTAL CASH COST
      for 1 full contract (already factoring in multiplier and commissions).
      For example, for an ES Futures Option with multiplier 50, if an option was traded
      at 90.97 points, IBKR reports `averageCost = 4548.59` ($4,548.59).
      If `averageCost` is left unscaled, `average_price` would be in total contract
      dollars ($4,548.59) while `market_price` is in index points (169.46 points),
      creating a 50x scale mismatch.

    - Resolution:
      For `FuturesOption` and `Option`, we divide `averageCost` by `multiplier` so that both
      `average_price` and `market_price` share the exact same unit of quotation (points or $/share).
      Downstream consumers can then uniformly calculate:
        cost_basis     = position * average_price * multiplier
        market_value   = position * market_price * multiplier
        unrealized_pnl = (market_price - average_price) * position * multiplier
    """
    is_derivative_option = isinstance(contract, (FuturesOption, Option)) or getattr(
        contract, "secType", ""
    ) in ("OPT", "FOP")

    if is_derivative_option and multiplier > 1:
        return average_cost / multiplier

    return average_cost


class IBKRService:
    """Synchronous, thread-safe service wrapping ib_async for IBKR queries."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        client_id: int | None = None,
        timeout: float | None = None,
        ports: list[int] | None = None,
    ):
        settings = get_settings()
        self.host = host if host is not None else settings.ibkr_host
        if port is not None:
            self.port = port
        elif ports:
            self.port = ports[0]
        else:
            self.port = settings.ibkr_port
        self.client_id = client_id if client_id is not None else settings.ibkr_client_id
        self.timeout = timeout if timeout is not None else settings.ibkr_timeout
        self._ib = IB()
        self._lock = threading.Lock()
        self._contract_name_cache: dict[int, str] = {}

    def is_connected(self) -> bool:
        """Check if currently connected to IBKR."""
        return self._ib.isConnected()

    def disconnect(self) -> None:
        """Disconnect active session."""
        with self._lock:
            if self._ib.isConnected():
                self._ib.disconnect()

    def _ensure_connected(self) -> None:
        """Connect to TWS on port 7496 if not already connected."""
        if self._ib.isConnected():
            return

        try:
            # readonly=True avoids requesting open orders/executions, connecting in ~0.1s
            self._ib.connect(
                self.host,
                self.port,
                clientId=self.client_id,
                readonly=True,
                timeout=self.timeout,
            )
            logger.info("Connected to IBKR TWS on %s:%d", self.host, self.port)
        except Exception as e:
            logger.warning("Failed to connect to IBKR TWS on %s:%d: %s", self.host, self.port, e)
            with contextlib.suppress(Exception):
                self._ib.disconnect()
            raise ConnectionError(
                f"Could not connect to IBKR TWS on {self.host}:{self.port} ({e}). "
                "Please ensure TWS is running with 'Enable ActiveX and Socket Clients' "
                f"enabled on port {self.port}."
            ) from e

    def get_accounts(self) -> list[str]:
        """Return list of managed account IDs, e.g. ['U16110728']."""
        with self._lock:
            self._ensure_connected()
            try:
                return list(self._ib.managedAccounts())
            except Exception as e:
                self.disconnect()
                raise ConnectionError(f"Error communicating with IBKR TWS: {e}") from e

    def get_account_values(self, account_id: str) -> AccountValues:
        """Return key account values and cash balance breakdown."""
        with self._lock:
            self._ensure_connected()
            try:
                accounts = self._ib.managedAccounts()
                if account_id not in accounts:
                    raise ValueError(
                        f"Account '{account_id}' not found. Available accounts: {accounts}"
                    )

                vals = self._ib.accountValues(account=account_id)
            except ValueError:
                raise
            except Exception as e:
                self.disconnect()
                raise ConnectionError(f"Error communicating with IBKR TWS: {e}") from e

            default_currency = "USD"
            available_funds = 0.0
            buying_power = 0.0
            excess_liquidity = 0.0
            maint_margin = 0.0
            cash_map: dict[str, float] = {}

            for v in vals:
                tag = v.tag
                curr = v.currency
                val_str = v.value

                if tag == "AvailableFunds" and (curr == default_currency or not curr):
                    with contextlib.suppress(ValueError):
                        available_funds = float(val_str)
                elif tag == "BuyingPower" and (curr == default_currency or not curr):
                    with contextlib.suppress(ValueError):
                        buying_power = float(val_str)
                elif tag == "ExcessLiquidity" and (curr == default_currency or not curr):
                    with contextlib.suppress(ValueError):
                        excess_liquidity = float(val_str)
                elif tag == "MaintMarginReq" and (curr == default_currency or not curr):
                    with contextlib.suppress(ValueError):
                        maint_margin = float(val_str)
                elif tag == "CashBalance" and curr and curr != "BASE":
                    with contextlib.suppress(ValueError):
                        cash_map[curr] = float(val_str)

            cash_balances = [
                CashBalanceItem(currency=c, amount=amt) for c, amt in sorted(cash_map.items())
            ]

            return AccountValues(
                available_funds=available_funds,
                buying_power=buying_power,
                excess_liquidity=excess_liquidity,
                maintenance_margin=maint_margin,
                currency=default_currency,
                cash_balances=cash_balances,
            )

    def get_positions(self, account_id: str) -> list[Position]:
        """Return raw positions for the specified account."""
        with self._lock:
            self._ensure_connected()
            try:
                accounts = self._ib.managedAccounts()
                if account_id not in accounts:
                    raise ValueError(
                        f"Account '{account_id}' not found. Available accounts: {accounts}"
                    )

                portfolio = self._ib.portfolio()
            except ValueError:
                raise
            except Exception as e:
                self.disconnect()
                raise ConnectionError(f"Error communicating with IBKR TWS: {e}") from e

            account_items = [p for p in portfolio if p.account == account_id]
            positions: list[Position] = []

            for item in account_items:
                c: Contract = item.contract

                # Retrieve instrument name with in-memory cache
                con_id = c.conId
                if con_id and con_id in self._contract_name_cache:
                    instrument_name = self._contract_name_cache[con_id]
                else:
                    instrument_name = c.symbol
                    try:
                        details = self._ib.reqContractDetails(c)
                        if details and details[0].longName:
                            instrument_name = details[0].longName
                            if con_id:
                                self._contract_name_cache[con_id] = instrument_name
                    except Exception:
                        pass

                # Parse contract multiplier
                mult = 1.0
                if c.multiplier:
                    with contextlib.suppress(ValueError):
                        mult = float(c.multiplier)
                if mult <= 0:
                    mult = 1.0

                # Normalise average unit price using dedicated derivative multiplier handler
                avg_price = _normalize_average_price(item.averageCost, c, mult)

                last_trade = c.lastTradeDateOrContractMonth or None
                strike = c.strike if (getattr(c, "strike", 0.0) and c.strike > 0) else None
                right = (
                    c.right
                    if (getattr(c, "right", None) and c.right not in ("0", "", "?"))
                    else None
                )
                prim_ex = c.primaryExchange or None

                positions.append(
                    Position(
                        instrument=instrument_name,
                        symbol=c.localSymbol or c.symbol,
                        position=item.position,
                        average_price=round(avg_price, 4),
                        market_price=round(item.marketPrice, 4),
                        multiplier=mult,
                        currency=c.currency or "USD",
                        primary_exchange=prim_ex,
                        last_trading_date=last_trade,
                        sec_type=c.secType or None,
                        strike=strike,
                        right=right,
                        underlying_symbol=c.symbol or None,
                        con_id=c.conId or None,
                    )
                )

            return positions


# Global singleton instance
ibkr_service = IBKRService()
