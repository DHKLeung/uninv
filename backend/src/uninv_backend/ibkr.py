"""Interactive Brokers connector service using ib_async."""

import contextlib
import logging
import math
import threading
import time
from datetime import UTC, datetime

from ib_async import IB, Contract, Forex, FuturesOption, Option

from uninv_backend.config import get_settings
from uninv_backend.models import (
    AccountValues,
    BrokerAccountSnapshot,
    CashBalanceItem,
    Currency,
    Exchange,
    OptionType,
    Position,
    SecurityType,
)

logger = logging.getLogger(__name__)

IBKR_SEC_TYPE_MAP: dict[str, SecurityType] = {
    "STK": SecurityType.STOCKS,
    "OPT": SecurityType.OPTIONS,
    "FOP": SecurityType.FUTURES_OPTIONS,
    "FUT": SecurityType.FUTURES,
    "CRYPTO": SecurityType.CRYPTO,
    "CASH": SecurityType.CASH,
}


def _format_date_str(d_str: str | None) -> str:
    """Format expiration date '20261218' to 'Dec18\'26'."""
    if not d_str or len(d_str) < 8:
        return d_str or ""
    try:
        dt = datetime.strptime(d_str[:8], "%Y%m%d")
        return f"{dt.strftime('%b%d')}'{dt.strftime('%y')}"
    except Exception:
        return d_str


def _format_date_iso(d_str: str | None) -> str | None:
    """Format expiration date '20261218' to '2026-12-18'."""
    if not d_str:
        return None
    d_clean = d_str.strip()
    if len(d_clean) >= 8 and d_clean[:8].isdigit():
        return f"{d_clean[:4]}-{d_clean[4:6]}-{d_clean[6:8]}"
    return d_clean


def _format_strike(strike: float | None) -> str:
    """Format strike price without trailing decimal if whole number."""
    if not strike:
        return ""
    return f"{int(strike)}" if strike.is_integer() else f"{strike}"


def _format_instrument_name(contract: Contract, fallback_name: str) -> str:
    """Format standardized instrument name.

    For options and futures options, builds names matching TWS screen:
    e.g. 'NVDA Jan19\'29 145 CALL' or 'ES FOP(EW3) Dec18\'26 7400 PUT'.
    For stocks and crypto, uses resolved longName (or fallback symbol).
    """
    sec = getattr(contract, "secType", "")
    if sec in ("OPT", "FOP", "FUT"):
        d_fmt = _format_date_str(getattr(contract, "lastTradeDateOrContractMonth", None))
        s_fmt = _format_strike(getattr(contract, "strike", None))
        raw_right = getattr(contract, "right", "")
        r_str = (
            "CALL" if raw_right in ("C", "CALL") else ("PUT" if raw_right in ("P", "PUT") else "")
        )

        if sec == "FOP":
            tc = getattr(contract, "tradingClass", "")
            tag = f"FOP({tc})" if tc else "FOP"
            parts = [contract.symbol, tag, d_fmt, s_fmt, r_str]
            return " ".join(p for p in parts if p)
        elif sec == "OPT":
            parts = [contract.symbol, d_fmt, s_fmt, r_str]
            return " ".join(p for p in parts if p)
        elif sec == "FUT":
            parts = [contract.symbol, d_fmt]
            return " ".join(p for p in parts if p)

    return fallback_name or contract.symbol


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
      `avg_price` and `mark_price` share the exact same unit of quotation (points or $/share).
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
        self._fx_cache: dict[tuple[Currency, Currency], tuple[float, float]] = {}

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

    def get_accounts(self) -> tuple[list[str], datetime]:
        """Return list of managed account IDs with query timestamp."""
        asof = datetime.now(UTC)
        with self._lock:
            self._ensure_connected()
            try:
                return list(self._ib.managedAccounts()), asof
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

            default_currency = Currency.USD
            available_funds = 0.0
            buying_power = 0.0
            cash_balance = 0.0
            equity_with_loan_value = 0.0
            excess_liquidity = 0.0
            gross_position_value = 0.0
            init_margin_req = 0.0
            maint_margin_req = 0.0
            net_liquidation = 0.0
            unrealized_pnl = 0.0
            cash_map: dict[Currency, float] = {}

            for v in vals:
                tag = v.tag
                curr_str = v.currency
                val_str = v.value

                # Strictly ignore artificial BASE rows
                if curr_str == "BASE":
                    continue

                if tag == "CashBalance" and curr_str:
                    try:
                        c_enum = Currency(curr_str)
                        amt = float(val_str)
                        cash_map[c_enum] = amt
                        if c_enum == default_currency:
                            cash_balance = amt
                    except ValueError:
                        raise ValueError(
                            f"Unsupported currency '{curr_str}' received in CashBalance"
                        ) from None

                elif tag == "AvailableFunds" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        available_funds = float(val_str)
                elif tag == "BuyingPower" and (curr_str == default_currency.value or not curr_str):
                    with contextlib.suppress(ValueError):
                        buying_power = float(val_str)
                elif tag == "EquityWithLoanValue" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        equity_with_loan_value = float(val_str)
                elif tag == "ExcessLiquidity" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        excess_liquidity = float(val_str)
                elif tag == "GrossPositionValue" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        gross_position_value = float(val_str)
                elif tag == "InitMarginReq" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        init_margin_req = float(val_str)
                elif tag == "MaintMarginReq" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        maint_margin_req = float(val_str)
                elif tag == "NetLiquidation" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        net_liquidation = float(val_str)
                elif tag == "UnrealizedPnL" and (
                    curr_str == default_currency.value or not curr_str
                ):
                    with contextlib.suppress(ValueError):
                        unrealized_pnl = float(val_str)

            cash_balances = [
                CashBalanceItem(currency=c, amount=amt)
                for c, amt in sorted(cash_map.items(), key=lambda x: x[0].value)
            ]

            return AccountValues(
                currency=default_currency,
                available_funds=available_funds,
                buying_power=buying_power,
                cash_balance=cash_balance,
                cash_balances=cash_balances,
                equity_with_loan_value=equity_with_loan_value,
                excess_liquidity=excess_liquidity,
                gross_position_value=gross_position_value,
                init_margin_req=init_margin_req,
                maint_margin_req=maint_margin_req,
                net_liquidation=net_liquidation,
                unrealized_pnl=unrealized_pnl,
            )

    def get_positions(self, account_id: str) -> list[Position]:
        """Return standardized holding positions with calculated cost basis and API values."""
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

                # Retrieve instrument longName with cache
                con_id = c.conId
                if con_id and con_id in self._contract_name_cache:
                    long_name = self._contract_name_cache[con_id]
                else:
                    long_name = c.symbol
                    try:
                        details = self._ib.reqContractDetails(c)
                        if details and details[0].longName:
                            long_name = details[0].longName
                            if con_id:
                                self._contract_name_cache[con_id] = long_name
                    except Exception:
                        pass

                # Standardized instrument name
                instrument_name = _format_instrument_name(c, long_name)

                # Parse contract multiplier
                mult = 1.0
                if c.multiplier:
                    with contextlib.suppress(ValueError):
                        mult = float(c.multiplier)
                if mult <= 0:
                    mult = 1.0

                # Normalise average unit price
                avg_price = float(_normalize_average_price(item.averageCost, c, mult))
                mark_price = float(item.marketPrice)

                # Cost basis = position * avg_price * multiplier (raw float, no display rounding)
                cost_basis = float(item.position * avg_price * mult)
                market_val = float(item.marketValue)
                unrealized_pnl = float(item.unrealizedPNL)

                # Currency validation (loud fail if unsupported)
                raw_curr = c.currency or "USD"
                try:
                    currency = Currency(raw_curr)
                except ValueError:
                    raise ValueError(
                        f"Unsupported currency '{raw_curr}' on position {c.symbol}"
                    ) from None

                # Exchange validation (loud fail if unsupported)
                raw_ex = c.primaryExchange or c.exchange or None
                exchange = None
                if raw_ex:
                    try:
                        exchange = Exchange(raw_ex)
                    except ValueError:
                        raise ValueError(
                            f"Unsupported exchange '{raw_ex}' on position {c.symbol}"
                        ) from None

                # Security type mapping (loud fail if unsupported)
                raw_sec = c.secType or "STK"
                if raw_sec in IBKR_SEC_TYPE_MAP:
                    sec_type = IBKR_SEC_TYPE_MAP[raw_sec]
                else:
                    try:
                        sec_type = SecurityType(raw_sec)
                    except ValueError:
                        raise ValueError(
                            f"Unsupported security type '{raw_sec}' on position {c.symbol}"
                        ) from None

                # Option type
                raw_right = c.right or None
                option_type = None
                if raw_right in ("C", "CALL"):
                    option_type = OptionType.CALL
                elif raw_right in ("P", "PUT"):
                    option_type = OptionType.PUT

                last_trade = _format_date_iso(c.lastTradeDateOrContractMonth)
                strike = c.strike if (getattr(c, "strike", 0.0) and c.strike > 0) else None

                positions.append(
                    Position(
                        instrument=instrument_name,
                        symbol=c.localSymbol or c.symbol,
                        position=float(item.position),
                        avg_price=avg_price,
                        mark_price=mark_price,
                        cost_basis=cost_basis,
                        market_value=market_val,
                        unrealized_pnl=unrealized_pnl,
                        multiplier=mult,
                        currency=currency,
                        exchange=exchange,
                        sec_type=sec_type,
                        last_trade_date=last_trade,
                        strike=strike,
                        option_type=option_type,
                    )
                )

            return positions

    def get_snapshot(self, account_id: str) -> BrokerAccountSnapshot:
        """Return combined account snapshot containing account values and open positions."""
        asof = datetime.now(UTC)
        values = self.get_account_values(account_id)
        positions = self.get_positions(account_id)
        return BrokerAccountSnapshot(
            broker_id="ibkr",
            account_id=account_id,
            asof=asof,
            account_values=values,
            positions=positions,
        )

    def _get_direct_forex_rate(self, pair: str) -> float | None:
        """Fetch live or closing rate for a Forex pair like 'EURUSD'."""
        try:
            contract = Forex(pair)
            self._ib.qualifyContracts(contract)
            tickers = self._ib.reqTickers(contract)
            self._ib.sleep(0.4)
            if tickers:
                t = tickers[0]
                price = t.marketPrice()
                if not math.isnan(price) and price > 0:
                    return price
                if t.close and not math.isnan(t.close) and t.close > 0:
                    return t.close
                if t.last and not math.isnan(t.last) and t.last > 0:
                    return t.last
        except Exception as e:
            logger.debug("Direct forex probe failed for %s: %s", pair, e)
        return None

    def get_fx_rate(self, base: Currency, quote: Currency) -> tuple[float, datetime]:
        """Return FX rate (1 unit of base = X units of quote) and query timestamp."""
        if base == quote:
            return 1.0, datetime.now(UTC)

        asof = datetime.now(UTC)
        with self._lock:
            self._ensure_connected()
            cache_key = (base, quote)
            now = time.time()
            if cache_key in self._fx_cache:
                rate, ts = self._fx_cache[cache_key]
                if now - ts < 15.0:  # 15 seconds TTL
                    return rate, asof

            # 1. Try direct pair
            direct_pair = f"{base.value}{quote.value}"
            rate = self._get_direct_forex_rate(direct_pair)
            if rate is not None and rate > 0:
                self._fx_cache[(base, quote)] = (rate, now)
                self._fx_cache[(quote, base)] = (1.0 / rate, now)
                return rate, asof

            # 2. Try inverted pair
            inverted_pair = f"{quote.value}{base.value}"
            inv_rate = self._get_direct_forex_rate(inverted_pair)
            if inv_rate is not None and inv_rate > 0:
                rate = 1.0 / inv_rate
                self._fx_cache[(base, quote)] = (rate, now)
                self._fx_cache[(quote, base)] = (inv_rate, now)
                return rate, asof

            # 3. Triangulate via USD
            if base != Currency.USD and quote != Currency.USD:
                rate_base_usd, _ = self.get_fx_rate(base, Currency.USD)
                rate_usd_quote, _ = self.get_fx_rate(Currency.USD, quote)
                triangulated = rate_base_usd * rate_usd_quote
                self._fx_cache[(base, quote)] = (triangulated, now)
                self._fx_cache[(quote, base)] = (1.0 / triangulated, now)
                return triangulated, asof

            raise ValueError(f"Could not resolve exchange rate for {base.value}/{quote.value}")


# Global singleton instance
ibkr_service = IBKRService()
