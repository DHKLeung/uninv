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


def test_positions_ibkr_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/ibkr-hk")
    assert resp.status_code == 200
    positions = resp.json()
    assert len(positions) == 6

    # Check required fields exist on every position
    for p in positions:
        assert "instrument" in p
        assert "symbol" in p
        assert "position" in p
        assert "average_price" in p
        assert "mark_price" in p
        assert "currency" in p
        assert "expiry_date" in p
        assert p["currency"] == "USD"
        # Ensure derived metrics are not returned by the backend API
        assert "market_value" not in p
        assert "cost_basis" not in p
        assert "unrealised_pnl" not in p

    # Verify options & futures options have expiry_date
    aapl_opt = next(p for p in positions if p["symbol"] == "AAPL 261218C00240000")
    assert aapl_opt["expiry_date"] == "2026-12-18"
    assert aapl_opt["multiplier"] == 100.0

    # Verify equity has null expiry_date
    aapl_stock = next(p for p in positions if p["symbol"] == "AAPL")
    assert aapl_stock["expiry_date"] is None

    # Verify Bitcoin position is present
    btc = next(p for p in positions if p["symbol"] == "BTC")
    assert btc["instrument"] == "Bitcoin"
    assert btc["position"] == 1.25
    assert btc["expiry_date"] is None


def test_positions_futubull_endpoint(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/futubull-hk")
    assert resp.status_code == 200
    positions = resp.json()
    assert len(positions) == 10

    # Filter by specific account
    acct_id = "1001279250287283"
    filtered = client.get(f"/api/v1/positions/futubull-hk?account_id={acct_id}").json()
    assert len(filtered) == 3
    assert all(p["account_id"] == acct_id for p in filtered)


def test_positions_unknown_account_404(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/futubull-hk?account_id=invalid-id")
    assert resp.status_code == 404


def test_positions_unknown_broker_404(client: TestClient) -> None:
    resp = client.get("/api/v1/positions/unknown-broker")
    assert resp.status_code == 404
