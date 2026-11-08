"""Futu OpenD broker connector service.

Connects to Futu OpenD (listening on localhost port 11111 by default)
using the official `futu-api` package.
Extracts live account margins, cash balances, and positions into uninv unified models.

All external calls are guarded with fast socket pre-checks to prevent blocking
when Futu OpenD is offline, and all operations enforce zero-cache live fetching.
"""

import contextlib
import logging
import re
import socket
import threading
from datetime import UTC, datetime
from typing import Any

import futu
import pandas as pd

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

# Configure futu-api defaults: ensure internal threads never prevent process termination
futu.SysConfig.set_all_thread_daemon(True)
futu.SysConfig.enable_console_log(False)

# Regex to detect and parse option codes:
# US: US.AAPL250117C00200000 or AAPL 250117C00200000
# HK: HK.TCH240627C380000
_OPTION_PATTERN = re.compile(r"^(?:[A-Z]{2}\.)?([A-Z0-9]+)\s*(\d{2})(\d{2})(\d{2})([CP])(\d{4,8})$")

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any raw API value (e.g. 'N/A', None, NaN) to float."""
    if val is None or pd.isna(val) or val == "N/A" or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _map_currency(cur_str: str | None, default: Currency = Currency.USD) -> Currency:
    """Safely map string currency code to Currency Enum."""
    if not cur_str:
        return default
    cur_norm = cur_str.strip().upper()
    if cur_norm in ("CNY", "RMB"):
        return Currency.CNH
    try:
        return Currency(cur_norm)
    except ValueError:
        return default


def _map_exchange(market_str: str | None, code: str) -> Exchange | None:
    """Infer exchange from market identifier or symbol prefix."""
    code_upper = code.upper()
    if code_upper.startswith("HK.") or market_str == "HK":
        return Exchange.SEHK
    if code_upper.startswith("SH.") or market_str in ("SH", "SSE"):
        return Exchange.SSE
    if code_upper.startswith("SZ.") or market_str in ("SZ", "SZSE"):
        return Exchange.SZSE
    if code_upper.startswith("CC.") or market_str == "CRYPTO":
        return Exchange.OSL
    return None


class FutuService:
    """Service interfacing with Futu OpenD daemon via futu-api."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        timeout: float | None = None,
    ):
        settings = get_settings()
        self.host = host or settings.futu_host
        self.port = port or settings.futu_port
        self.timeout = timeout or settings.futu_timeout
        self._sec_ctx: futu.OpenSecTradeContext | None = None
        self._crypto_ctx: futu.OpenCryptoTradeContext | None = None
        self._crypto_accounts: set[str] = set()
        self._lock = threading.Lock()

    def is_opend_available(self, timeout: float = 0.3) -> bool:
        """Probe if Futu OpenD TCP port is actively accepting connections."""
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    def _get_sec_context(self) -> futu.OpenSecTradeContext:
        """Retrieve or create an active OpenSecTradeContext."""
        if not self.is_opend_available():
            raise ConnectionError(
                f"Cannot connect to Futu OpenD on {self.host}:{self.port}. "
                "Please ensure Futu OpenD is running and logged in."
            )

        if (
            self._sec_ctx is not None
            and getattr(self._sec_ctx, "status", None) == futu.ContextStatus.READY
        ):
            return self._sec_ctx

        try:
            if self._sec_ctx is not None:
                with contextlib.suppress(Exception):
                    self._sec_ctx.close()
            self._sec_ctx = futu.OpenSecTradeContext(
                filter_trdmarket=futu.TrdMarket.NONE,
                host=self.host,
                port=self.port,
            )
            return self._sec_ctx
        except Exception as e:
            self._sec_ctx = None
            raise ConnectionError(f"Failed to connect to Futu OpenD securities context: {e}") from e

    def _get_crypto_context(self) -> futu.OpenCryptoTradeContext:
        """Retrieve or create an active OpenCryptoTradeContext."""
        if not self.is_opend_available():
            raise ConnectionError(
                f"Cannot connect to Futu OpenD on {self.host}:{self.port}. "
                "Please ensure Futu OpenD is running and logged in."
            )

        if (
            self._crypto_ctx is not None
            and getattr(self._crypto_ctx, "status", None) == futu.ContextStatus.READY
        ):
            return self._crypto_ctx

        try:
            if self._crypto_ctx is not None:
                with contextlib.suppress(Exception):
                    self._crypto_ctx.close()
            self._crypto_ctx = futu.OpenCryptoTradeContext(
                host=self.host,
                port=self.port,
            )
            return self._crypto_ctx
        except Exception as e:
            self._crypto_ctx = None
            raise ConnectionError(f"Failed to connect to Futu OpenD crypto context: {e}") from e

    def get_accounts(self) -> tuple[list[str], datetime]:
        """Fetch list of active account IDs (securities + crypto) from Futu OpenD."""
        with self._lock:
            accounts: list[str] = []
            asof = datetime.now(UTC)

            # 1. Fetch securities accounts
            sec_ctx = self._get_sec_context()
            ret_sec, data_sec = sec_ctx.get_acc_list()
            if ret_sec == futu.RET_OK and isinstance(data_sec, pd.DataFrame) and not data_sec.empty:
                filtered = data_sec
                if "trd_env" in data_sec.columns:
                    filtered = filtered[filtered["trd_env"].astype(str).str.upper() == "REAL"]
                if "acc_status" in filtered.columns:
                    filtered = filtered[filtered["acc_status"].astype(str).str.upper() == "ACTIVE"]
                for _, row in filtered.iterrows():
                    acc_id = str(row["acc_id"])
                    if acc_id not in accounts:
                        accounts.append(acc_id)

            # 2. Fetch crypto accounts
            try:
                crypto_ctx = self._get_crypto_context()
                ret_c, data_c = crypto_ctx.get_acc_list()
                if ret_c == futu.RET_OK and isinstance(data_c, pd.DataFrame) and not data_c.empty:
                    filtered_c = data_c
                    if "trd_env" in data_c.columns:
                        filtered_c = filtered_c[
                            filtered_c["trd_env"].astype(str).str.upper() == "REAL"
                        ]
                    if "acc_status" in filtered_c.columns:
                        filtered_c = filtered_c[
                            filtered_c["acc_status"].astype(str).str.upper() == "ACTIVE"
                        ]
                    for _, row in filtered_c.iterrows():
                        acc_id = str(row["acc_id"])
                        self._crypto_accounts.add(acc_id)
                        if acc_id not in accounts:
                            accounts.append(acc_id)
            except Exception as e:
                logger.warning("Futu crypto accounts fetch skipped: %s", e)

            return accounts, asof

    def get_snapshot(self, account_id: str) -> BrokerAccountSnapshot:
        """Fetch complete live snapshot (AccountValues + Positions) for an account."""
        with self._lock:
            try:
                acc_id_int = int(account_id)
            except ValueError as err:
                raise ValueError(f"Invalid Futu account ID: {account_id}") from err

            # Select context based on account type
            is_crypto = account_id in self._crypto_accounts
            ctx = self._get_crypto_context() if is_crypto else self._get_sec_context()

            # 1. Fetch positions with refresh_cache=True (zero-cache live snapshot)
            ret_pos, pos_df = ctx.position_list_query(
                acc_id=acc_id_int,
                refresh_cache=True,
            )
            if ret_pos != futu.RET_OK:
                # If first attempt failed and we weren't sure of context, try the other context
                if not is_crypto:
                    try:
                        c_ctx = self._get_crypto_context()
                        r_p, p_df = c_ctx.position_list_query(
                            acc_id=acc_id_int, refresh_cache=True
                        )
                        if r_p == futu.RET_OK:
                            self._crypto_accounts.add(account_id)
                            ctx = c_ctx
                            pos_df = p_df
                            ret_pos = r_p
                    except Exception:
                        pass
                if ret_pos != futu.RET_OK:
                    raise ConnectionError(f"Futu position_list_query failed: {pos_df}")

            # 2. Fetch account asset information with refresh_cache=True
            ret_acc, acc_df = ctx.accinfo_query(
                acc_id=acc_id_int,
                refresh_cache=True,
            )
            if ret_acc != futu.RET_OK:
                raise ConnectionError(f"Futu accinfo_query failed: {acc_df}")

            asof = datetime.now(UTC)
            positions = self._parse_positions(pos_df)
            account_values = self._parse_account_values(acc_df, positions=positions)

            return BrokerAccountSnapshot(
                broker_id="futu",
                account_id=account_id,
                asof=asof,
                account_values=account_values,
                positions=positions,
            )

    def _parse_account_values(
        self,
        df: Any,
        positions: list[Position] | None = None,
    ) -> AccountValues:
        """Convert Futu accinfo_query DataFrame into AccountValues model."""
        if not isinstance(df, pd.DataFrame) or df.empty:
            return AccountValues(
                currency=Currency.USD,
                available_funds=0.0,
                buying_power=0.0,
                cash_balance=0.0,
                cash_balances=[],
                equity_with_loan_value=0.0,
                excess_liquidity=0.0,
                gross_position_value=0.0,
                init_margin_req=0.0,
                maint_margin_req=0.0,
                net_liquidation=0.0,
                unrealized_pnl=0.0,
            )

        row = df.iloc[0]
        cur_raw = str(row.get("currency", "USD"))
        base_currency = _map_currency(cur_raw, Currency.USD)

        net_liq = _safe_float(row.get("total_assets"), 0.0)
        gross_pos = _safe_float(row.get("market_val"), 0.0)
        if gross_pos == 0.0:
            gross_pos = _safe_float(row.get("crypto_mv"), 0.0)
        cash = _safe_float(row.get("cash"), 0.0)
        power = _safe_float(row.get("power"), 0.0)
        avl_funds = _safe_float(row.get("available_funds"), power)
        init_margin = _safe_float(row.get("initial_margin"), 0.0)
        maint_margin = _safe_float(row.get("maintenance_margin"), 0.0)

        excess_liq = max(0.0, net_liq - maint_margin) if maint_margin > 0 else avl_funds

        # Unrealized P&L: if accinfo_query returns 'N/A', estimate from positions
        unrealized = _safe_float(row.get("unrealized_pl"), 0.0)
        if unrealized == 0.0 and positions:
            pos_pnl_sum = sum(p.unrealized_pnl for p in positions)
            pos_mv_sum = sum(p.market_value for p in positions)
            if pos_mv_sum > 0 and gross_pos > 0:
                effective_fx = gross_pos / pos_mv_sum
                unrealized = pos_pnl_sum * effective_fx
            else:
                unrealized = pos_pnl_sum

        # Build multi-currency cash balances list
        cash_balances: list[CashBalanceItem] = []
        currency_cash_map = [
            ("hk_cash", Currency.HKD),
            ("us_cash", Currency.USD),
            ("cn_cash", Currency.CNH),
            ("jp_cash", Currency.JPY),
            ("sg_cash", Currency.SGD),
            ("au_cash", Currency.AUD),
            ("ca_cash", Currency.CAD),
        ]
        for col_name, currency_enum in currency_cash_map:
            if col_name in row:
                amount = _safe_float(row[col_name], 0.0)
                if abs(amount) > 1e-6:
                    cash_balances.append(CashBalanceItem(currency=currency_enum, amount=amount))

        # If no breakdown exists, populate with base cash balance
        if not cash_balances and abs(cash) > 1e-6:
            cash_balances.append(CashBalanceItem(currency=base_currency, amount=cash))

        return AccountValues(
            currency=base_currency,
            available_funds=avl_funds,
            buying_power=power,
            cash_balance=cash,
            cash_balances=cash_balances,
            equity_with_loan_value=net_liq,
            excess_liquidity=excess_liq,
            gross_position_value=gross_pos,
            init_margin_req=init_margin,
            maint_margin_req=maint_margin,
            net_liquidation=net_liq,
            unrealized_pnl=unrealized,
        )

    def _parse_positions(self, df: Any) -> list[Position]:
        """Convert Futu position_list_query DataFrame into Position list."""
        if not isinstance(df, pd.DataFrame) or df.empty:
            return []

        positions: list[Position] = []
        for _, row in df.iterrows():
            code = str(row.get("code", "")).strip()
            if not code:
                continue

            # Strip market prefix for clean contract symbol (e.g. "US.AAPL" -> "AAPL")
            symbol = code
            if "." in code:
                symbol = code.split(".", 1)[1]

            stock_name = str(row.get("stock_name", symbol)).strip()
            qty = _safe_float(row.get("qty"), 0.0)
            side = str(row.get("position_side", "LONG")).upper()
            if side == "SHORT" and qty > 0:
                qty = -qty

            cost_price = _safe_float(row.get("cost_price"), 0.0)
            avg_price = cost_price if cost_price > 0 else _safe_float(row.get("average_cost"), 0.0)
            mark_price = _safe_float(row.get("nominal_price"), 0.0)
            market_val = _safe_float(row.get("market_val"), 0.0)
            unrealized_raw = _safe_float(row.get("unrealized_pl"), 0.0)
            unrealized_pl = (
                unrealized_raw if unrealized_raw != 0.0 else _safe_float(row.get("pl_val"), 0.0)
            )

            market_str = str(row.get("position_market", "")).strip()
            exchange = _map_exchange(market_str, code)

            # Determine trading currency
            cur_col = row.get("currency")
            currency = (
                _map_currency(str(cur_col))
                if pd.notna(cur_col) and str(cur_col) != "N/A"
                else None
            )
            if not currency:
                if market_str == "HK" or code.upper().startswith("HK."):
                    currency = Currency.HKD
                elif market_str in ("SH", "SZ", "CN") or code.upper().startswith(("SH.", "SZ.")):
                    currency = Currency.CNH
                else:
                    currency = Currency.USD

            # Check if this position is crypto or option
            is_crypto = market_str == "CRYPTO" or code.upper().startswith("CC.")
            opt_match = _OPTION_PATTERN.match(code) if not is_crypto else None

            if is_crypto:
                instrument = stock_name
                multiplier = 1.0
                sec_type = SecurityType.CRYPTO
                strike = None
                option_type = None
                last_trade_date = None
            elif opt_match:
                underlying, yy, mm, dd, cp, strike_str = opt_match.groups()
                month_idx = int(mm) - 1
                month_abbr = _MONTH_NAMES[month_idx] if 0 <= month_idx < 12 else mm
                strike = (
                    int(strike_str) / 1000.0 if len(strike_str) == 8 else float(strike_str) / 1000.0
                )
                option_type = OptionType.CALL if cp == "C" else OptionType.PUT
                last_trade_date = f"20{yy}-{mm}-{dd}"
                multiplier = 100.0  # standard equity options multiplier
                instrument = f"{underlying} {month_abbr}{dd}'{yy} {strike:g} {option_type.value}"
                sec_type = SecurityType.OPTIONS
            else:
                instrument = stock_name
                multiplier = 1.0
                sec_type = SecurityType.STOCKS
                strike = None
                option_type = None
                last_trade_date = None

            cost_basis = qty * avg_price * multiplier

            positions.append(
                Position(
                    instrument=instrument,
                    symbol=symbol,
                    position=qty,
                    avg_price=avg_price,
                    mark_price=mark_price,
                    cost_basis=cost_basis,
                    market_value=market_val,
                    unrealized_pnl=unrealized_pl,
                    multiplier=multiplier,
                    currency=currency,
                    exchange=exchange,
                    sec_type=sec_type,
                    last_trade_date=last_trade_date,
                    strike=strike,
                    option_type=option_type,
                )
            )

        return positions

    def close(self) -> None:
        """Close open context connections."""
        with self._lock:
            if self._sec_ctx is not None:
                with contextlib.suppress(Exception):
                    self._sec_ctx.close()
                self._sec_ctx = None
            if self._crypto_ctx is not None:
                with contextlib.suppress(Exception):
                    self._crypto_ctx.close()
                self._crypto_ctx = None


futu_service = FutuService()
