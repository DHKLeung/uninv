"""Futu OpenD broker connector service.

Connects to Futu OpenD (listening on localhost port 11111 by default)
using the official `futu-api` package.
Extracts live account margins, cash balances, and positions into uninv unified models.

Operates at the Universal Account (uni_card_num) level:
- Traverses all Trade Contexts (Securities, Futures, Crypto).
- Uses filter_trdmarket=TrdMarket.NONE for Securities to prevent silent market filtering.
- Loops through all SecurityFirm enum values to capture all Futu & Moomoo broker subsidiaries.
- Queries account values in USD (currency="USD").
- Filters cash balances with high confidence (preserves fractional dust > 1e-8).
- Aggregates sub-accounts into their parent Universal Account.
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

# Discover all real SecurityFirm enum values (excluding NONE / 'N/A')
ALL_SECURITY_FIRMS: list[str] = [
    getattr(futu.SecurityFirm, attr)
    for attr in dir(futu.SecurityFirm)
    if not attr.startswith("_")
    and not callable(getattr(futu.SecurityFirm, attr))
    and getattr(futu.SecurityFirm, attr) != futu.SecurityFirm.NONE
]

# Regex to detect and parse option codes:
# US: US.AAPL250117C00200000 or AAPL 250117C00200000
# HK: HK.TCH240627C380000
_OPTION_PATTERN = re.compile(r"^(?:[A-Z]{2}\.)?([A-Z0-9]+)\s*(\d{2})(\d{2})(\d{2})([CP])(\d{4,8})$")

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

CASH_COLUMN_MAP: list[tuple[str, Currency]] = [
    ("us_cash", Currency.USD),
    ("hk_cash", Currency.HKD),
    ("cn_cash", Currency.CNH),
    ("jp_cash", Currency.JPY),
    ("sg_cash", Currency.SGD),
    ("au_cash", Currency.AUD),
    ("ca_cash", Currency.CAD),
]


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
    """Infer exchange from market identifier or symbol prefix when clearly defined."""
    code_upper = code.upper()
    if code_upper.startswith("HK.") or market_str == "HK":
        return Exchange.SEHK
    if code_upper.startswith("SH.") or market_str in ("SH", "SSE"):
        return Exchange.SSE
    if code_upper.startswith("SZ.") or market_str in ("SZ", "SZSE"):
        return Exchange.SZSE
    # Crypto or unspecified exchange defaults to None
    return None


class FutuService:
    """Meta-broker service interfacing with Futu OpenD daemon via futu-api."""

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
        # Map: uni_card_num -> list of (context_type, firm, acc_id)
        self._universal_accounts_map: dict[str, list[tuple[str, str, int]]] = {}
        self._lock = threading.Lock()

    def set_gateway(self, host: str | None = None, port: int | None = None) -> None:
        """Update Futu OpenD gateway host/port and clear discovered account mappings."""
        with self._lock:
            if host and self.host != host.strip():
                self.host = host.strip()
                self._universal_accounts_map.clear()
            if port and self.port != port:
                self.port = port
                self._universal_accounts_map.clear()

    def set_port(self, port: int) -> None:
        """Update Futu OpenD gateway port and clear discovered account mappings."""
        self.set_gateway(port=port)

    def test_connection(self) -> tuple[bool, str]:
        """Test if Futu OpenD daemon is reachable."""
        if self.is_opend_available():
            return True, f"Connected to Futu OpenD on {self.host}:{self.port}"
        return False, f"Cannot reach Futu OpenD on {self.host}:{self.port}"

    def is_opend_available(self, timeout: float = 0.3) -> bool:
        """Probe if Futu OpenD TCP port is actively accepting connections."""
        try:
            with socket.create_connection((self.host, self.port), timeout=timeout):
                return True
        except OSError:
            return False

    def _discover_universal_accounts(self) -> dict[str, list[tuple[str, str, int]]]:
        """Query all contexts and security firms to build the complete Universal Account mapping."""
        if not self.is_opend_available():
            raise ConnectionError(
                f"Cannot connect to Futu OpenD on {self.host}:{self.port}. "
                "Please ensure Futu OpenD is running and logged in."
            )

        uni_map: dict[str, list[tuple[str, str, int]]] = {}

        # 1. Securities Context across all firms
        for firm in ALL_SECURITY_FIRMS:
            try:
                ctx = futu.OpenSecTradeContext(
                    filter_trdmarket=futu.TrdMarket.NONE,
                    security_firm=firm,
                    host=self.host,
                    port=self.port,
                )
                ret, df = ctx.get_acc_list()
                if ret == futu.RET_OK and isinstance(df, pd.DataFrame) and not df.empty:
                    real = df[(df["trd_env"] == "REAL") & (df["acc_status"] == "ACTIVE")]
                    for _, row in real.iterrows():
                        uni_card = str(row["uni_card_num"]).strip()
                        acc_id = int(row["acc_id"])
                        uni_map.setdefault(uni_card, []).append(("SEC", firm, acc_id))
                ctx.close()
            except Exception as e:
                logger.debug("Sec context scan for firm %s failed: %s", firm, e)

        # 2. Futures Context across all firms
        for firm in ALL_SECURITY_FIRMS:
            try:
                ctx = futu.OpenFutureTradeContext(
                    security_firm=firm,
                    host=self.host,
                    port=self.port,
                )
                ret, df = ctx.get_acc_list()
                if ret == futu.RET_OK and isinstance(df, pd.DataFrame) and not df.empty:
                    real = df[(df["trd_env"] == "REAL") & (df["acc_status"] == "ACTIVE")]
                    for _, row in real.iterrows():
                        uni_card = str(row["uni_card_num"]).strip()
                        acc_id = int(row["acc_id"])
                        uni_map.setdefault(uni_card, []).append(("FUT", firm, acc_id))
                ctx.close()
            except Exception as e:
                logger.debug("Future context scan for firm %s failed: %s", firm, e)

        # 3. Crypto Context across all firms
        for firm in ALL_SECURITY_FIRMS:
            try:
                ctx = futu.OpenCryptoTradeContext(
                    security_firm=firm,
                    host=self.host,
                    port=self.port,
                )
                ret, df = ctx.get_acc_list()
                if ret == futu.RET_OK and isinstance(df, pd.DataFrame) and not df.empty:
                    real = df[(df["trd_env"] == "REAL") & (df["acc_status"] == "ACTIVE")]
                    for _, row in real.iterrows():
                        uni_card = str(row["uni_card_num"]).strip()
                        acc_id = int(row["acc_id"])
                        uni_map.setdefault(uni_card, []).append(("CRYPTO", firm, acc_id))
                ctx.close()
            except Exception as e:
                logger.debug("Crypto context scan for firm %s failed: %s", firm, e)

        self._universal_accounts_map = uni_map
        return uni_map

    def get_accounts(self) -> tuple[list[str], datetime]:
        """Fetch list of all active Universal Account IDs across all Futu and Moomoo entities."""
        with self._lock:
            uni_map = self._discover_universal_accounts()
            asof = datetime.now(UTC)
            return list(uni_map.keys()), asof

    def get_snapshot(self, account_id: str) -> BrokerAccountSnapshot:
        """Fetch complete live snapshot (AccountValues + Positions) for a Universal Account."""
        with self._lock:
            if not self.is_opend_available():
                raise ConnectionError(
                    f"Cannot connect to Futu OpenD on {self.host}:{self.port}. "
                    "Please ensure Futu OpenD is running and logged in."
                )

            # Discover or refresh accounts mapping
            if account_id not in self._universal_accounts_map:
                self._discover_universal_accounts()

            if account_id not in self._universal_accounts_map:
                raise ValueError(
                    f"Universal account '{account_id}' not found. "
                    f"Available accounts: {list(self._universal_accounts_map.keys())}"
                )

            sub_accounts = self._universal_accounts_map[account_id]

            total_assets = 0.0
            total_gross_mv = 0.0
            total_maint_margin = 0.0
            total_fund_assets = 0.0
            total_bond_assets = 0.0
            all_positions: list[Position] = []
            cash_by_currency: dict[Currency, float] = {}
            fallback_unrealized_pnl = 0.0

            for c_type, firm, sub_acc_id in sub_accounts:
                ctx = None
                try:
                    if c_type == "SEC":
                        ctx = futu.OpenSecTradeContext(
                            filter_trdmarket=futu.TrdMarket.NONE,
                            security_firm=firm,
                            host=self.host,
                            port=self.port,
                        )
                    elif c_type == "FUT":
                        ctx = futu.OpenFutureTradeContext(
                            security_firm=firm,
                            host=self.host,
                            port=self.port,
                        )
                    else:
                        ctx = futu.OpenCryptoTradeContext(
                            security_firm=firm,
                            host=self.host,
                            port=self.port,
                        )

                    # 1. Query live positions with zero-cache
                    ret_pos, pos_df = ctx.position_list_query(
                        acc_id=sub_acc_id,
                        refresh_cache=True,
                    )
                    if ret_pos == futu.RET_OK and isinstance(pos_df, pd.DataFrame):
                        positions = self._parse_positions(pos_df)
                        all_positions.extend(positions)

                    # 2. Query live account margins & balances in USD
                    ret_info, info_df = ctx.accinfo_query(
                        acc_id=sub_acc_id,
                        currency="USD",
                        refresh_cache=True,
                    )
                    if (
                        ret_info == futu.RET_OK
                        and isinstance(info_df, pd.DataFrame)
                        and not info_df.empty
                    ):
                        row = info_df.iloc[0]
                        total_assets += _safe_float(row.get("total_assets"), 0.0)
                        pos_mv = _safe_float(row.get("market_val"), 0.0)
                        crypto_mv = _safe_float(row.get("crypto_mv"), 0.0)
                        fund_mv = _safe_float(row.get("fund_assets"), 0.0)
                        bond_mv = _safe_float(row.get("bond_assets"), 0.0)
                        total_fund_assets += fund_mv
                        total_bond_assets += bond_mv
                        total_gross_mv += pos_mv + crypto_mv + fund_mv + bond_mv
                        total_maint_margin += _safe_float(row.get("maintenance_margin"), 0.0)
                        fallback_unrealized_pnl += _safe_float(row.get("unrealized_pl"), 0.0)

                        # Accumulate multi-currency cash balances
                        for col_name, currency_enum in CASH_COLUMN_MAP:
                            if col_name in row:
                                amt = _safe_float(row.get(col_name), 0.0)
                                if abs(amt) > 1e-8:
                                    cash_by_currency[currency_enum] = (
                                        cash_by_currency.get(currency_enum, 0.0) + amt
                                    )
                finally:
                    if ctx is not None:
                        with contextlib.suppress(Exception):
                            ctx.close()

            # Append synthetic holding rows for fund and bond assets if details cannot be retrieved
            if total_fund_assets > 1e-8:
                all_positions.append(
                    Position(
                        instrument="Fund Assets",
                        symbol=None,
                        position=total_fund_assets,
                        avg_price=None,
                        mark_price=1.0,
                        cost_basis=None,
                        market_value=total_fund_assets,
                        unrealized_pnl=0.0,
                        multiplier=1.0,
                        currency=Currency.USD,
                        exchange=None,
                        sec_type=SecurityType.FUNDS,
                    )
                )

            if total_bond_assets > 1e-8:
                all_positions.append(
                    Position(
                        instrument="Bond Assets",
                        symbol=None,
                        position=total_bond_assets,
                        avg_price=None,
                        mark_price=1.0,
                        cost_basis=None,
                        market_value=total_bond_assets,
                        unrealized_pnl=0.0,
                        multiplier=1.0,
                        currency=Currency.USD,
                        exchange=None,
                        sec_type=SecurityType.BONDS,
                    )
                )

            # Calculate total unrealized P&L from positions, or fall back to accinfo
            if all_positions:
                total_unrealized_pnl = sum(p.unrealized_pnl for p in all_positions)
            else:
                total_unrealized_pnl = fallback_unrealized_pnl

            # If gross position value is 0 but we have positions, sum their market values
            if total_gross_mv == 0.0 and all_positions:
                total_gross_mv = sum(p.market_value for p in all_positions)

            # Build multi-currency cash balance breakdown (strictly non-zero)
            cash_balances = [
                CashBalanceItem(currency=c, amount=amt)
                for c, amt in sorted(cash_by_currency.items(), key=lambda x: x[0].value)
                if abs(amt) > 1e-8
            ]

            excess_liquidity = max(0.0, total_assets - total_maint_margin)
            cash_balance = total_assets - total_gross_mv

            account_values = AccountValues(
                currency=Currency.USD,
                net_liquidation=total_assets,
                gross_position_value=total_gross_mv,
                cash_balance=cash_balance,
                maint_margin_req=total_maint_margin,
                excess_liquidity=excess_liquidity,
                unrealized_pnl=total_unrealized_pnl,
                cash_balances=cash_balances,
            )

            asof = datetime.now(UTC)

            return BrokerAccountSnapshot(
                broker_id="futu",
                account_id=account_id,
                asof=asof,
                account_values=account_values,
                positions=all_positions,
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

            # Use the broker's native symbol code (e.g. "US.TSM", "CC.BTC")
            symbol = code
            stock_name = str(row.get("stock_name", symbol)).strip()
            qty = _safe_float(row.get("qty"), 0.0)
            side = str(row.get("position_side", "LONG")).upper()
            if side == "SHORT" and qty > 0:
                qty = -qty

            avg_cost = _safe_float(row.get("average_cost"), 0.0)
            cost_price = _safe_float(row.get("cost_price"), 0.0)
            avg_price = avg_cost if avg_cost > 0 else cost_price
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
                _map_currency(str(cur_col)) if pd.notna(cur_col) and str(cur_col) != "N/A" else None
            )
            if not currency:
                if market_str == "HK" or code.upper().startswith("HK."):
                    currency = Currency.HKD
                elif market_str in ("SH", "SZ", "CN") or code.upper().startswith(("SH.", "SZ.")):
                    currency = Currency.CNH
                else:
                    currency = Currency.USD

            # Check if this position is crypto, futures, or option
            is_crypto = market_str == "CRYPTO" or code.upper().startswith("CC.")
            is_future = market_str == "FUTURES" or code.upper().startswith("FM.")
            opt_match = _OPTION_PATTERN.match(code) if (not is_crypto and not is_future) else None

            if is_crypto:
                instrument = stock_name
                multiplier = 1.0
                sec_type = SecurityType.CRYPTO
                strike = None
                option_type = None
                last_trading_date = None
            elif is_future:
                instrument = stock_name
                multiplier = 1.0
                sec_type = SecurityType.FUTURES
                strike = None
                option_type = None
                last_trading_date = None
            elif opt_match:
                underlying, yy, mm, dd, cp, strike_str = opt_match.groups()
                month_idx = int(mm) - 1
                month_abbr = _MONTH_NAMES[month_idx] if 0 <= month_idx < 12 else mm
                strike = (
                    int(strike_str) / 1000.0 if len(strike_str) == 8 else float(strike_str) / 1000.0
                )
                option_type = OptionType.CALL if cp == "C" else OptionType.PUT
                last_trading_date = f"20{yy}-{mm}-{dd}"
                multiplier = 100.0  # standard equity options multiplier
                instrument = f"{underlying} {month_abbr}{dd}'{yy} {strike:g} {option_type.value}"
                sec_type = SecurityType.OPTIONS
            else:
                instrument = stock_name
                multiplier = 1.0
                sec_type = SecurityType.STOCKS
                strike = None
                option_type = None
                last_trading_date = None

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
                    last_trading_date=last_trading_date,
                    strike=strike,
                    option_type=option_type,
                )
            )

        return positions


futu_service = FutuService()
