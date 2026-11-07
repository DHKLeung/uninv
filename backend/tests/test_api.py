from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from uninv_backend.app import app
from uninv_backend.models import AccountValues, CashBalanceItem, Position


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


def test_account_values_endpoint(client: TestClient) -> None:
    mock_values = AccountValues(
        available_funds=42138.60,
        buying_power=280923.98,
        excess_liquidity=48390.88,
        maintenance_margin=51633.95,
        currency="USD",
        cash_balances=[
            CashBalanceItem(currency="USD", amount=-6612.62),
            CashBalanceItem(currency="HKD", amount=12500.00),
        ],
    )
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_account_values",
        return_value=mock_values,
    ):
        resp = client.get("/api/v1/account-values?broker_id=ibkr&account_id=U16110728")
        assert resp.status_code == 200
        data = resp.json()
        assert data["available_funds"] == 42138.60
        assert data["buying_power"] == 280923.98
        assert data["excess_liquidity"] == 48390.88
        assert data["maintenance_margin"] == 51633.95
        assert data["currency"] == "USD"
        assert len(data["cash_balances"]) == 2
        assert data["cash_balances"][0] == {"currency": "USD", "amount": -6612.62}
        assert data["cash_balances"][1] == {"currency": "HKD", "amount": 12500.00}


def test_account_values_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/account-values?broker_id=futubull&account_id=U16110728")
    assert resp.status_code == 404


def test_account_values_unknown_account_404(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_account_values",
        side_effect=ValueError("Account 'invalid' not found"),
    ):
        resp = client.get("/api/v1/account-values?broker_id=ibkr&account_id=invalid")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


def test_positions_endpoint(client: TestClient) -> None:
    mock_positions = [
        Position(
            instrument="ALPHA ARCHITECT 1-3 MNTH BOX",
            symbol="BOXX",
            position=463.0,
            average_price=115.5847,
            market_price=118.95,
            multiplier=1.0,
            currency="USD",
            primary_exchange="BATS",
            last_trading_date=None,
            sec_type="STK",
            strike=None,
            right=None,
            underlying_symbol="BOXX",
            con_id=604408720,
        ),
        Position(
            instrument="ALPHABET INC-CL A",
            symbol="GOOGL 290119C00230000",
            position=1.0,
            average_price=96.6577,
            market_price=100.7369,
            multiplier=100.0,
            currency="USD",
            primary_exchange="AMEX",
            last_trading_date="20290119",
            sec_type="OPT",
            strike=230.0,
            right="C",
            underlying_symbol="GOOGL",
            con_id=924079172,
        ),
    ]

    with patch(
        "uninv_backend.api.routes.ibkr_service.get_positions",
        return_value=mock_positions,
    ):
        resp = client.get("/api/v1/positions?broker_id=ibkr&account_id=U16110728")
        assert resp.status_code == 200
        positions = resp.json()
        assert len(positions) == 2

        # Check raw non-derived fields
        boxx = positions[0]
        assert boxx["instrument"] == "ALPHA ARCHITECT 1-3 MNTH BOX"
        assert boxx["symbol"] == "BOXX"
        assert boxx["position"] == 463.0
        assert boxx["average_price"] == 115.5847
        assert boxx["market_price"] == 118.95
        assert boxx["multiplier"] == 1.0
        assert boxx["currency"] == "USD"
        assert boxx["primary_exchange"] == "BATS"
        assert boxx["last_trading_date"] is None
        assert boxx["sec_type"] == "STK"
        # Ensure no derived metrics are returned
        assert "market_value" not in boxx
        assert "cost_basis" not in boxx
        assert "unrealized_pnl" not in boxx

        googl = positions[1]
        assert googl["instrument"] == "ALPHABET INC-CL A"
        assert googl["symbol"] == "GOOGL 290119C00230000"
        assert googl["multiplier"] == 100.0
        assert googl["strike"] == 230.0
        assert googl["right"] == "C"
        assert googl["last_trading_date"] == "20290119"


def test_positions_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/positions?broker_id=unknown&account_id=U16110728")
    assert resp.status_code == 404


def test_positions_unknown_account_404(client: TestClient) -> None:
    with patch(
        "uninv_backend.api.routes.ibkr_service.get_positions",
        side_effect=ValueError("Account 'invalid' not found"),
    ):
        resp = client.get("/api/v1/positions?broker_id=ibkr&account_id=invalid")
        assert resp.status_code == 404


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
