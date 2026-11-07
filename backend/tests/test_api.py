from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from uninv_backend.app import app
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
    assert brokers == [{"id": "ibkr", "name": "Interactive Brokers"}]


def test_accounts_endpoint(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_accounts",
        return_value=["U16110728"],
    ):
        resp = client.get("/api/v1/accounts?broker_id=ibkr")
        assert resp.status_code == 200
        assert resp.json() == ["U16110728"]


def test_accounts_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/accounts?broker_id=unknown-broker")
    assert resp.status_code == 404
    assert "not supported" in resp.json()["detail"]


def test_accounts_service_unavailable_503(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_accounts",
        side_effect=ConnectionError("Could not connect to IBKR gateway"),
    ):
        resp = client.get("/api/v1/accounts?broker_id=ibkr")
        assert resp.status_code == 503
        assert "Could not connect to IBKR gateway" in resp.json()["detail"]


def test_snapshot_endpoint(client: TestClient) -> None:
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
            last_trading_date=None,
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
            last_trading_date="20290119",
            strike=145.0,
            option_type=OptionType.CALL,
        ),
    ]

    mock_snapshot = BrokerAccountSnapshot(
        broker_id="ibkr",
        account_id="U16110728",
        account_values=mock_values,
        positions=mock_positions,
    )

    with patch(
        "uninv_backend.api.routes.ibkr_service.get_snapshot",
        return_value=mock_snapshot,
    ):
        resp = client.get("/api/v1/snapshot?broker_id=ibkr&account_id=U16110728")
        assert resp.status_code == 200
        data = resp.json()
        assert data["broker_id"] == "ibkr"
        assert data["account_id"] == "U16110728"

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
        assert boxx["option_type"] is None

        nvda = positions[1]
        assert nvda["instrument"] == "NVDA Jan19'29 145 CALL"
        assert nvda["multiplier"] == 100.0
        assert nvda["strike"] == 145.0
        assert nvda["option_type"] == "CALL"
        assert nvda["sec_type"] == "OPTIONS"
        assert nvda["cost_basis"] == 7081.85
        assert nvda["market_value"] == 7497.76


def test_snapshot_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/snapshot?broker_id=futubull&account_id=U16110728")
    assert resp.status_code == 404


def test_snapshot_unknown_account_404(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_snapshot",
        side_effect=ValueError("Account 'invalid' not found"),
    ):
        resp = client.get("/api/v1/snapshot?broker_id=ibkr&account_id=invalid")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


def test_fx_endpoint(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_fx_rate",
        return_value=1.1219,
    ):
        resp = client.get("/api/v1/fx?base=EUR&quote=USD")
        assert resp.status_code == 200
        data = resp.json()
        assert data["base"] == "EUR"
        assert data["quote"] == "USD"
        assert data["rate"] == 1.1219


def test_fx_endpoint_same_currency(client: TestClient) -> None:
    resp = client.get("/api/v1/fx?base=USD&quote=USD")
    assert resp.status_code == 200
    assert resp.json() == {"base": "USD", "quote": "USD", "rate": 1.0}


def test_fx_endpoint_invalid_currency_422(client: TestClient) -> None:
    resp = client.get("/api/v1/fx?base=INVALID&quote=USD")
    assert resp.status_code == 422


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


def test_ibkr_service_connect_failure_raises_connection_error_with_reason() -> None:
    from uninv_backend.ibkr import IBKRService

    # Use a dummy non-existent port to test connection failure immediately
    service = IBKRService(host="127.0.0.1", port=59999, timeout=0.1)
    with pytest.raises(ConnectionError) as exc_info:
        service._ensure_connected()
    assert "Could not connect to IBKR TWS on 127.0.0.1:59999" in str(exc_info.value)
    assert "port 59999" in str(exc_info.value)

    # Also verify default port 7496
    default_service = IBKRService()
    assert default_service.port == 7496


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
