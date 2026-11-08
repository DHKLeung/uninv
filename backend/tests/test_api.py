from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from uninv_backend.app import app
from uninv_backend.models import (
    AccountValues,
    BrokerAccountSnapshot,
    CashBalanceItem,
    Currency,
    Exchange,
    FxMatrixResponse,
    OptionType,
    Position,
    SecurityType,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_root_redirects_to_docs(client: TestClient) -> None:
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"] == "/docs"


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_supporting_brokers_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/supporting-brokers")
    assert resp.status_code == 200
    brokers = resp.json()
    assert brokers == [
        {"id": "ibkr", "name": "Interactive Brokers"},
        {"id": "futu", "name": "Futubull"},
    ]


def test_accounts_endpoint(client: TestClient) -> None:
    test_dt = datetime(2026, 11, 7, 23, 0, 0, tzinfo=UTC)
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_accounts",
        new_callable=AsyncMock,
        return_value=(["U16110728"], test_dt),
    ):
        resp = client.get("/api/v1/accounts?broker_id=ibkr")
        assert resp.status_code == 200
        data = resp.json()
        assert data["broker_id"] == "ibkr"
        assert data["accounts"] == ["U16110728"]
        assert "2026-11-07T23:00:00" in data["asof"]


def test_accounts_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/accounts?broker_id=unknown-broker")
    assert resp.status_code == 404
    assert "not supported" in resp.json()["detail"]


def test_accounts_service_unavailable_503(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_accounts",
        new_callable=AsyncMock,
        side_effect=ConnectionError("Could not connect to IBKR gateway"),
    ):
        resp = client.get("/api/v1/accounts?broker_id=ibkr")
        assert resp.status_code == 503
        assert "Could not connect to IBKR gateway" in resp.json()["detail"]


def test_snapshot_endpoint(client: TestClient) -> None:
    test_dt = datetime(2026, 11, 7, 23, 0, 0, tzinfo=UTC)
    mock_values = AccountValues(
        currency=Currency.USD,
        available_funds=42138.60,
        buying_power=280923.98,
        cash_balance=-6612.62,
        cash_balances=[
            CashBalanceItem(currency=Currency.USD, amount=-6612.62),
            CashBalanceItem(currency=Currency.HKD, amount=12500.00),
        ],
        equity_with_loan_value=99883.58,
        excess_liquidity=48390.88,
        gross_position_value=123573.20,
        init_margin_req=57744.98,
        maint_margin_req=51623.57,
        net_liquidation=100014.45,
        unrealized_pnl=-2783.42,
    )

    mock_positions = [
        Position(
            instrument="ALPHA ARCHITECT 1-3 MNTH BOX",
            symbol="BOXX",
            position=463.0,
            avg_price=115.5847,
            mark_price=118.95,
            cost_basis=53515.72,
            market_value=55073.85,
            unrealized_pnl=1558.13,
            multiplier=1.0,
            currency=Currency.USD,
            exchange=Exchange.BATS,
            sec_type=SecurityType.STOCKS,
            last_trade_date=None,
            strike=None,
            option_type=None,
        ),
        Position(
            instrument="NVDA Jan19'29 145 CALL",
            symbol="NVDA  290119C00145000",
            position=1.0,
            avg_price=70.8185,
            mark_price=74.9776,
            cost_basis=7081.85,
            market_value=7497.76,
            unrealized_pnl=415.91,
            multiplier=100.0,
            currency=Currency.USD,
            exchange=Exchange.AMEX,
            sec_type=SecurityType.OPTIONS,
            last_trade_date="2029-01-19",
            strike=145.0,
            option_type=OptionType.CALL,
        ),
    ]

    mock_snapshot = BrokerAccountSnapshot(
        broker_id="ibkr",
        account_id="U16110728",
        asof=test_dt,
        account_values=mock_values,
        positions=mock_positions,
    )

    with patch(
        "uninv_backend.api.routes.ibkr_service.get_snapshot",
        new_callable=AsyncMock,
        return_value=mock_snapshot,
    ):
        resp = client.get("/api/v1/snapshot?broker_id=ibkr&account_id=U16110728")
        assert resp.status_code == 200
        data = resp.json()
        assert data["broker_id"] == "ibkr"
        assert data["account_id"] == "U16110728"
        assert "2026-11-07T23:00:00" in data["asof"]

        # Check account values
        av = data["account_values"]
        assert av["currency"] == "USD"
        assert av["available_funds"] == 42138.60
        assert av["buying_power"] == 280923.98
        assert av["cash_balance"] == -6612.62
        assert av["net_liquidation"] == 100014.45
        assert av["unrealized_pnl"] == -2783.42
        assert len(av["cash_balances"]) == 2

        # Check positions
        positions = data["positions"]
        assert len(positions) == 2

        boxx = positions[0]
        assert boxx["instrument"] == "ALPHA ARCHITECT 1-3 MNTH BOX"
        assert boxx["symbol"] == "BOXX"
        assert boxx["position"] == 463.0
        assert boxx["avg_price"] == 115.5847
        assert boxx["mark_price"] == 118.95
        assert boxx["cost_basis"] == 53515.72
        assert boxx["market_value"] == 55073.85
        assert boxx["unrealized_pnl"] == 1558.13
        assert boxx["exchange"] == "BATS"
        assert boxx["sec_type"] == "STOCKS"
        assert boxx["last_trade_date"] is None
        assert boxx["option_type"] is None

        nvda = positions[1]
        assert nvda["instrument"] == "NVDA Jan19'29 145 CALL"
        assert nvda["multiplier"] == 100.0
        assert nvda["strike"] == 145.0
        assert nvda["option_type"] == "CALL"
        assert nvda["sec_type"] == "OPTIONS"
        assert nvda["last_trade_date"] == "2029-01-19"
        assert nvda["cost_basis"] == 7081.85
        assert nvda["market_value"] == 7497.76


def test_snapshot_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/snapshot?broker_id=futubull&account_id=U16110728")
    assert resp.status_code == 404


def test_snapshot_unknown_account_404(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_snapshot",
        new_callable=AsyncMock,
        side_effect=ValueError("Account 'invalid' not found"),
    ):
        resp = client.get("/api/v1/snapshot?broker_id=ibkr&account_id=invalid")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


def test_fx_matrix_endpoint(client: TestClient) -> None:
    test_dt = datetime(2026, 11, 7, 23, 0, 0, tzinfo=UTC)
    mock_matrix = FxMatrixResponse(
        asof=test_dt,
        currencies=list(Currency),
        rates={
            Currency.USD: {Currency.USD: 1.0, Currency.EUR: 0.92},
            Currency.EUR: {Currency.USD: 1.08, Currency.EUR: 1.0},
        },
    )
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_fx_matrix",
        new_callable=AsyncMock,
        return_value=mock_matrix,
    ):
        resp = client.get("/api/v1/fx")
        assert resp.status_code == 200
        data = resp.json()
        assert "2026-11-07T23:00:00" in data["asof"]
        assert "USD" in data["currencies"]
        assert len(data["currencies"]) == len(Currency)
        assert data["rates"]["USD"]["EUR"] == 0.92
        assert data["rates"]["EUR"]["USD"] == 1.08


def test_format_date_iso() -> None:
    from uninv_backend.ibkr import _format_date_iso

    assert _format_date_iso("20261218") == "2026-12-18"
    assert _format_date_iso("20290119") == "2029-01-19"
    assert _format_date_iso(None) is None
    assert _format_date_iso("") is None


def test_derivative_instrument_name_formatter() -> None:
    from ib_async import FuturesOption, Option, Stock

    from uninv_backend.ibkr import _format_instrument_name

    # 1. Equity Option
    opt = Option(
        symbol="NVDA",
        lastTradeDateOrContractMonth="20290119",
        strike=145.0,
        right="C",
    )
    name_opt = _format_instrument_name(opt, "NVIDIA CORP")
    assert name_opt == "NVDA Jan19'29 145 CALL"

    # 2. Futures Option
    fop = FuturesOption(
        symbol="ES",
        lastTradeDateOrContractMonth="20261218",
        strike=7400.0,
        right="P",
        tradingClass="EW3",
    )
    name_fop = _format_instrument_name(fop, "E-mini S&P 500")
    assert name_fop == "ES FOP(EW3) Dec18'26 7400 PUT"

    # 3. Stock uses longName fallback
    stk = Stock(symbol="BOXX")
    name_stk = _format_instrument_name(stk, "ALPHA ARCHITECT 1-3 MNTH BOX")
    assert name_stk == "ALPHA ARCHITECT 1-3 MNTH BOX"


def test_normalize_average_price_for_derivatives() -> None:
    from ib_async import Crypto, FuturesOption, Option, Stock

    from uninv_backend.ibkr import _normalize_average_price

    # 1. FuturesOption (multiplier 50)
    fop = FuturesOption(symbol="ES", strike=7400.0, right="P", multiplier="50")
    norm_fop = _normalize_average_price(average_cost=4548.59, contract=fop, multiplier=50.0)
    assert round(norm_fop, 4) == 90.9718

    # 2. Equity Option (multiplier 100)
    opt = Option(symbol="GOOGL", strike=230.0, right="C", multiplier="100")
    norm_opt = _normalize_average_price(average_cost=9665.7673, contract=opt, multiplier=100.0)
    assert round(norm_opt, 4) == 96.6577

    # 3. Stock (multiplier 1.0)
    stk = Stock(symbol="BOXX")
    norm_stk = _normalize_average_price(average_cost=115.5847, contract=stk, multiplier=1.0)
    assert norm_stk == 115.5847

    # 4. Crypto (multiplier 1.0)
    crypto = Crypto(symbol="BTC")
    norm_crypto = _normalize_average_price(average_cost=70729.40, contract=crypto, multiplier=1.0)
    assert norm_crypto == 70729.40


@pytest.mark.anyio
async def test_ibkr_service_connect_failure_raises_connection_error_with_reason() -> None:
    from uninv_backend.ibkr import IBKRService

    # Use a dummy non-existent port to test connection failure immediately
    service = IBKRService(host="127.0.0.1", port=59999, timeout=0.1)
    with pytest.raises(ConnectionError) as exc_info:
        await service.ensure_connected()
    assert "Could not connect to IBKR TWS on 127.0.0.1:59999" in str(exc_info.value)
    assert "port 59999" in str(exc_info.value)

    # Also verify default port 7496
    default_service = IBKRService()
    assert default_service.port == 7496


def test_string_normalization_and_whitespace_collapse() -> None:
    # Test that multiple consecutive spaces are collapsed and strings stripped
    pos = Position(
        instrument="  NVDA   Jan19'29    145    CALL  ",
        symbol="NVDA  290119C00145000",
        position=1.0,
        avg_price=70.8185,
        mark_price=74.9776,
        cost_basis=7081.85,
        market_value=7497.76,
        unrealized_pnl=415.91,
        multiplier=100.0,
        currency=Currency.USD,
        exchange=Exchange.AMEX,
        sec_type=SecurityType.OPTIONS,
        last_trade_date="2029-01-19",
        strike=145.0,
        option_type=OptionType.CALL,
    )
    assert pos.instrument == "NVDA Jan19'29 145 CALL"
    assert pos.symbol == "NVDA 290119C00145000"


def test_endpoint_returns_503_when_tws_unreachable(client: TestClient) -> None:
    from uninv_backend.api import routes
    from uninv_backend.ibkr import IBKRService

    # Swap in a service pointing to a closed port to simulate TWS being offline
    offline_service = IBKRService(host="127.0.0.1", port=59999, timeout=0.1)
    with patch.object(routes, "ibkr_service", offline_service):
        resp = client.get("/api/v1/accounts?broker_id=ibkr")
        assert resp.status_code == 503
        data = resp.json()
        assert "Could not connect to IBKR TWS on 127.0.0.1:59999" in data["detail"]
        assert "Please ensure TWS is running" in data["detail"]


@pytest.mark.anyio
async def test_fx_router_get_matrix() -> None:
    from uninv_backend.fx import FxRouter

    market_quotes = {
        "EURUSD": 1.0850,
        "USDHKD": 7.8413,
        "USDJPY": 150.00,
    }

    router = FxRouter()
    matrix = await router.get_matrix(
        lambda pairs: {p: market_quotes[p] for p in pairs if p in market_quotes}
    )
    assert matrix.asof is not None
    assert len(matrix.currencies) == len(Currency)
    assert matrix.rates[Currency.EUR][Currency.USD] == 1.0850
    assert matrix.rates[Currency.USD][Currency.USD] == 1.0
    assert round(matrix.rates[Currency.EUR][Currency.HKD], 2) == round(1.0850 * 7.8413, 2)


@pytest.mark.anyio
async def test_fx_router_direct_and_inverted() -> None:
    from uninv_backend.fx import FxRouter

    market_quotes = {
        "EURUSD": 1.0850,
        "USDHKD": 7.8413,
    }

    router = FxRouter()

    # Direct EUR -> USD
    rate, _ = await router.get_rate(
        Currency.EUR,
        Currency.USD,
        lambda pairs: {p: market_quotes[p] for p in pairs if p in market_quotes},
    )
    assert rate == 1.0850

    # Inverted USD -> EUR
    rate_inv, _ = await router.get_rate(
        Currency.USD,
        Currency.EUR,
        lambda pairs: {p: market_quotes[p] for p in pairs if p in market_quotes},
    )
    assert round(rate_inv, 6) == round(1.0 / 1.0850, 6)


@pytest.mark.anyio
async def test_fx_router_cross_rate_synthesis() -> None:
    from uninv_backend.fx import FxRouter

    # Simulating standard IDEALPRO pairs where CAD -> HKD routes via USD hub
    # 1 USD = 1.402 CAD => 1 CAD = 1/1.402 USD
    # 1 USD = 7.8413 HKD
    # Expected CAD -> HKD: (1 / 1.402) * 7.8413 = 5.592938...
    market_quotes = {
        "USDCAD": 1.4020,
        "USDHKD": 7.8413,
    }

    router = FxRouter()
    rate, _ = await router.get_rate(
        Currency.CAD,
        Currency.HKD,
        lambda pairs: {p: market_quotes[p] for p in pairs if p in market_quotes},
    )
    expected = (1.0 / 1.4020) * 7.8413
    assert round(rate, 4) == round(expected, 4)


@pytest.mark.anyio
async def test_fx_router_fallback_on_missing_quote() -> None:
    from uninv_backend.fx import DEFAULT_USD_RATES, FxRouter

    router = FxRouter()
    # Empty market quotes -> uses DEFAULT_USD_RATES fallback
    rate, _ = await router.get_rate(Currency.EUR, Currency.USD, lambda pairs: {})
    assert rate == DEFAULT_USD_RATES[Currency.EUR]


@pytest.mark.anyio
async def test_fx_router_async_matrix() -> None:
    from uninv_backend.fx import FxRouter

    router = FxRouter()

    async def mock_async_probe(pairs: list[str]) -> dict[str, float]:
        return {"EURUSD": 1.10}

    matrix = await router.get_matrix(mock_async_probe)
    assert matrix.rates[Currency.EUR][Currency.USD] == 1.10
    assert matrix.rates[Currency.USD][Currency.USD] == 1.0


@pytest.mark.anyio
async def test_ibkr_service_async_concurrency() -> None:
    import asyncio

    from uninv_backend.ibkr import IBKRService

    service = IBKRService(host="127.0.0.1", port=59999, timeout=0.1)

    # Calling from multiple concurrent async tasks must raise ConnectionError cleanly
    # without deadlocking or raising event loop errors
    async def worker() -> Exception | None:
        try:
            await service.get_accounts()
            return None
        except ConnectionError as e:
            return e

    results = await asyncio.gather(*(worker() for _ in range(5)))
    assert len(results) == 5
    for err in results:
        assert err is not None
        assert "Could not connect to IBKR TWS" in str(err)


def test_futu_accounts_endpoint(client: TestClient) -> None:
    test_dt = datetime(2026, 11, 8, 14, 0, 0, tzinfo=UTC)
    with patch(
        "uninv_backend.api.routes.futu_service.get_accounts",
        return_value=(["28173918"], test_dt),
    ):
        resp = client.get("/api/v1/accounts?broker_id=futu")
        assert resp.status_code == 200
        data = resp.json()
        assert data["broker_id"] == "futu"
        assert data["accounts"] == ["28173918"]
        assert "2026-11-08T14:00:00" in data["asof"]


def test_futu_accounts_service_unavailable_503(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.futu_service.get_accounts",
        side_effect=ConnectionError("Cannot connect to Futu OpenD on 127.0.0.1:11111"),
    ):
        resp = client.get("/api/v1/accounts?broker_id=futu")
        assert resp.status_code == 503
        assert "Cannot connect to Futu OpenD" in resp.json()["detail"]


def test_futu_snapshot_endpoint(client: TestClient) -> None:
    test_dt = datetime(2026, 11, 8, 14, 0, 0, tzinfo=UTC)
    mock_snapshot = BrokerAccountSnapshot(
        broker_id="futu",
        account_id="28173918",
        asof=test_dt,
        account_values=AccountValues(
            currency=Currency.HKD,
            available_funds=150000.0,
            buying_power=300000.0,
            cash_balance=100000.0,
            cash_balances=[
                CashBalanceItem(currency=Currency.HKD, amount=80000.0),
                CashBalanceItem(currency=Currency.USD, amount=2500.0),
            ],
            equity_with_loan_value=500000.0,
            excess_liquidity=150000.0,
            gross_position_value=400000.0,
            init_margin_req=50000.0,
            maint_margin_req=30000.0,
            net_liquidation=500000.0,
            unrealized_pnl=25000.0,
        ),
        positions=[
            Position(
                instrument="Tencent Holdings",
                symbol="00700",
                position=500.0,
                avg_price=350.0,
                mark_price=400.0,
                cost_basis=175000.0,
                market_value=200000.0,
                unrealized_pnl=25000.0,
                multiplier=1.0,
                currency=Currency.HKD,
                exchange=Exchange.SEHK,
                sec_type=SecurityType.STOCKS,
            )
        ],
    )
    with patch(
        "uninv_backend.api.routes.futu_service.get_snapshot",
        return_value=mock_snapshot,
    ):
        resp = client.get("/api/v1/snapshot?broker_id=futu&account_id=28173918")
        assert resp.status_code == 200
        data = resp.json()
        assert data["broker_id"] == "futu"
        assert data["account_id"] == "28173918"
        assert data["account_values"]["net_liquidation"] == 500000.0
        assert len(data["positions"]) == 1
        assert data["positions"][0]["symbol"] == "00700"


def test_futu_snapshot_service_unavailable_503(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.futu_service.get_snapshot",
        side_effect=ConnectionError("Cannot connect to Futu OpenD"),
    ):
        resp = client.get("/api/v1/snapshot?broker_id=futu&account_id=28173918")
        assert resp.status_code == 503
        assert "Cannot connect to Futu OpenD" in resp.json()["detail"]


def test_futu_service_is_opend_available_offline() -> None:
    from uninv_backend.futu import FutuService

    service = FutuService(host="127.0.0.1", port=59998)
    assert service.is_opend_available(timeout=0.1) is False


def test_futu_service_parse_account_values() -> None:
    import pandas as pd

    from uninv_backend.futu import FutuService

    service = FutuService()
    df = pd.DataFrame(
        [
            {
                "currency": "HKD",
                "total_assets": 1250000.0,
                "market_val": 850000.0,
                "cash": 400000.0,
                "power": 600000.0,
                "available_funds": 350000.0,
                "initial_margin": 120000.0,
                "maintenance_margin": 80000.0,
                "unrealized_pl": 45000.0,
                "hk_cash": 300000.0,
                "us_cash": 12820.5,
                "cn_cash": 0.0,
            }
        ]
    )
    vals = service._parse_account_values(df)
    assert vals.currency == Currency.HKD
    assert vals.net_liquidation == 1250000.0
    assert vals.gross_position_value == 850000.0
    assert vals.cash_balance == 400000.0
    assert vals.buying_power == 600000.0
    assert vals.available_funds == 350000.0
    assert vals.init_margin_req == 120000.0
    assert vals.maint_margin_req == 80000.0
    assert vals.unrealized_pnl == 45000.0
    assert len(vals.cash_balances) == 2
    assert vals.cash_balances[0].currency == Currency.HKD
    assert vals.cash_balances[0].amount == 300000.0
    assert vals.cash_balances[1].currency == Currency.USD
    assert vals.cash_balances[1].amount == 12820.5


def test_futu_service_parse_positions() -> None:
    import pandas as pd

    from uninv_backend.futu import FutuService

    service = FutuService()
    df = pd.DataFrame(
        [
            {
                "code": "HK.00700",
                "stock_name": "Tencent Holdings",
                "qty": 300.0,
                "position_side": "LONG",
                "cost_price": 380.0,
                "nominal_price": 420.0,
                "market_val": 126000.0,
                "unrealized_pl": 12000.0,
                "position_market": "HK",
            },
            {
                "code": "US.NVDA250117C00145000",
                "stock_name": "NVIDIA Option",
                "qty": 2.0,
                "position_side": "LONG",
                "cost_price": 12.5,
                "nominal_price": 18.0,
                "market_val": 3600.0,
                "unrealized_pl": 1100.0,
                "position_market": "US",
            },
        ]
    )
    positions = service._parse_positions(df)
    assert len(positions) == 2

    # Stock
    p0 = positions[0]
    assert p0.symbol == "00700"
    assert p0.instrument == "Tencent Holdings"
    assert p0.position == 300.0
    assert p0.avg_price == 380.0
    assert p0.mark_price == 420.0
    assert p0.cost_basis == 300.0 * 380.0
    assert p0.market_value == 126000.0
    assert p0.unrealized_pnl == 12000.0
    assert p0.currency == Currency.HKD
    assert p0.exchange == Exchange.SEHK
    assert p0.sec_type == SecurityType.STOCKS

    # Option
    p1 = positions[1]
    assert p1.symbol == "NVDA250117C00145000"
    assert p1.instrument == "NVDA Jan17'25 145 CALL"
    assert p1.position == 2.0
    assert p1.avg_price == 12.5
    assert p1.mark_price == 18.0
    assert p1.cost_basis == 2.0 * 12.5 * 100.0
    assert p1.market_value == 3600.0
    assert p1.unrealized_pnl == 1100.0
    assert p1.currency == Currency.USD
    assert p1.sec_type == SecurityType.OPTIONS
    assert p1.option_type == OptionType.CALL
    assert p1.strike == 145.0
    assert p1.last_trade_date == "2025-01-17"
    assert p1.multiplier == 100.0
