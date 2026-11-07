import pytest
from fastapi.testclient import TestClient

from uninv_backend.app import app


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


def test_brokers_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/brokers")
    assert resp.status_code == 200
    brokers = resp.json()
    assert len(brokers) == 2
    assert brokers == [
        {"id": "ibkr-hk", "name": "Interactive Brokers (Hong Kong)"},
        {"id": "futubull-hk", "name": "Futubull (Hong Kong)"},
    ]


def test_accounts_ibkr_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/accounts/ibkr-hk")
    assert resp.status_code == 200
    accounts = resp.json()
    assert len(accounts) == 1
    assert accounts[0] == {
        "account_id": "U16110728",
        "broker_id": "ibkr-hk",
        "alias": "IBKR-HK (0728)",
    }


def test_accounts_futubull_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/accounts/futubull-hk")
    assert resp.status_code == 200
    accounts = resp.json()
    assert len(accounts) == 3
    assert [a["alias"] for a in accounts] == [
        "Futubull-HK (7283)",
        "Futubull-HK (7612)",
        "Futubull-HK (0281)",
    ]
    assert [a["account_id"] for a in accounts] == [
        "1001279250287283",
        "1001281798927612",
        "1001272756530281",
    ]


def test_accounts_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/accounts/unknown-broker")
    assert resp.status_code == 404


def test_cash_balance_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/cash-balance/ibkr-hk?account_id=U16110728")
    assert resp.status_code == 200
    data = resp.json()
    assert data == {
        "broker_id": "ibkr-hk",
        "account_id": "U16110728",
        "cash_balance": -6612.62,
        "currency": "USD",
    }

    # All accounts for broker
    all_resp = client.get("/api/v1/cash-balance/ibkr-hk")
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 1

    # Futubull cash balances
    futu_resp = client.get("/api/v1/cash-balance/futubull-hk")
    assert futu_resp.status_code == 200
    assert len(futu_resp.json()) == 3


def test_cash_balance_unknown_404(client: TestClient) -> None:
    assert client.get("/api/v1/cash-balance/unknown-broker").status_code == 404
    assert (
        client.get(
            "/api/v1/cash-balance/ibkr-hk?account_id=invalid-account"
        ).status_code
        == 404
    )


def test_positions_ibkr_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/ibkr-hk")
    assert resp.status_code == 200
    positions = resp.json()
    assert len(positions) == 12

    # Check required fields exist on every position
    for p in positions:
        assert "instrument" in p
        assert "symbol" in p
        assert "position" in p
        assert "average_price" in p
        assert "mark_price" in p
        assert "currency" in p
        assert "expiry_date" in p
        assert "delivery_date" in p
        assert p["currency"] == "USD"
        # Ensure derived metrics are not computed by the backend API for standard positions
        assert p["market_value"] is None
        assert p["cost_basis"] is None

    # Verify stock options
    googl_opt = next(p for p in positions if p["symbol"] == "GOOGL290119P00230000")
    assert googl_opt["instrument"] == "GOOGL Jan 19 '29 230 Put"
    assert googl_opt["expiry_date"] == "2029-01-19"
    assert googl_opt["delivery_date"] is None
    assert googl_opt["multiplier"] == 100.0

    nvda_opt = next(p for p in positions if p["symbol"] == "NVDA290119C00145000")
    assert nvda_opt["instrument"] == "NVDA Jan 19 '29 145 Call"
    assert nvda_opt["expiry_date"] == "2029-01-19"
    assert nvda_opt["delivery_date"] is None
    assert nvda_opt["multiplier"] == 100.0

    # Verify futures option
    es_fopt = next(p for p in positions if p["symbol"] == "ESH27 7400P 261218")
    assert es_fopt["instrument"] == "E-mini S&P 500 Mar 19 '27 7400 Put Dec 18 '26"
    assert es_fopt["expiry_date"] == "2026-12-18"
    assert es_fopt["delivery_date"] is None
    assert es_fopt["multiplier"] == 50.0

    # Verify Bitcoin position is present
    btc = next(p for p in positions if p["symbol"] == "BTC")
    assert btc["instrument"] == "Bitcoin"
    assert btc["position"] == 0.05981
    assert btc["mark_price"] == 75851.50
    assert btc["average_price"] == 70729.40

    # Verify QLD leveraged ETF
    qld = next(p for p in positions if p["symbol"] == "QLD")
    assert qld["position"] == 111.13
    assert qld["mark_price"] == 74.36
    assert qld["average_price"] == 78.64


def test_positions_futubull_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/futubull-hk")
    assert resp.status_code == 200
    positions = resp.json()
    assert len(positions) == 6

    # Verify money market fund without units / prices
    mmf = next(p for p in positions if p["symbol"] == "HK0000923844")
    assert mmf["instrument"] == "ChinaAMC Select USD Money Market Fund"
    assert mmf["position"] is None
    assert mmf["average_price"] is None
    assert mmf["mark_price"] is None
    assert mmf["market_value"] == 54565.17

    # Filter account 7283
    acct_7283 = client.get(
        "/api/v1/positions/futubull-hk?account_id=1001279250287283"
    ).json()
    assert len(acct_7283) == 5

    # Filter account 0281 (BTC)
    acct_0281 = client.get(
        "/api/v1/positions/futubull-hk?account_id=1001272756530281"
    ).json()
    assert len(acct_0281) == 1
    assert acct_0281[0]["symbol"] == "BTC"
    assert acct_0281[0]["position"] == 0.0791

    # Filter account 7612 (empty)
    acct_7612 = client.get(
        "/api/v1/positions/futubull-hk?account_id=1001281798927612"
    ).json()
    assert len(acct_7612) == 0


def test_positions_unknown_account_404(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/futubull-hk?account_id=invalid-id")
    assert resp.status_code == 404


def test_positions_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/unknown-broker")
    assert resp.status_code == 404
