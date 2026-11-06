import pytest
from fastapi.testclient import TestClient

from uninv_backend.api.routes import get_portfolio_service
from uninv_backend.app import app
from uninv_backend.brokers.base import BrokerConnector
from uninv_backend.brokers.mock import mock_futu, mock_ibkr
from uninv_backend.fx import StaticFxProvider
from uninv_backend.models import Broker
from uninv_backend.portfolio.service import PortfolioService


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_portfolio_totals_are_consistent(client: TestClient) -> None:
    data = client.get("/api/v1/portfolio").json()
    totals = data["totals"]

    assert data["base_currency"] == "USD"
    assert totals["net_liquidation"] == pytest.approx(totals["positions_value"] + totals["cash"])
    assert sum(p["market_value_base"] for p in data["positions"]) == pytest.approx(
        totals["positions_value"]
    )
    # Asset-class and currency breakdowns include cash, so they cover 100%.
    assert sum(s["weight"] for s in data["by_asset_class"]) == pytest.approx(1.0)
    assert sum(s["weight"] for s in data["by_currency"]) == pytest.approx(1.0)
    assert sum(a["weight"] for a in data["accounts"]) == pytest.approx(1.0)
    assert data["errors"] == []


def test_portfolio_covers_all_mock_brokers(client: TestClient) -> None:
    data = client.get("/api/v1/portfolio").json()
    assert {b["id"] for b in data["brokers"]} == {"ibkr", "futu", "schwab"}
    assert len(data["accounts"]) == 4


def test_symbol_consolidated_across_brokers(client: TestClient) -> None:
    data = client.get("/api/v1/portfolio").json()
    msft = next(s for s in data["by_symbol"] if s["key"] == "MSFT")
    assert msft["position_count"] == 2  # IBKR + Schwab


def test_hkd_positions_converted_to_base(client: TestClient) -> None:
    data = client.get("/api/v1/portfolio").json()
    tencent = next(p for p in data["positions"] if p["symbol"] == "0700.HK")
    assert tencent["currency"] == "HKD"
    assert tencent["market_value_base"] == pytest.approx(tencent["market_value"] * 0.1285)


def test_option_uses_multiplier(client: TestClient) -> None:
    data = client.get("/api/v1/portfolio").json()
    opt = next(p for p in data["positions"] if p["asset_class"] == "option")
    assert opt["market_value"] == pytest.approx(opt["quantity"] * opt["market_price"] * 100)
    assert opt["option"]["underlying"] == "AAPL"


def test_positions_filter_by_group(client: TestClient) -> None:
    resp = client.get("/api/v1/positions", params={"group_id": "hong-kong"})
    assert resp.status_code == 200
    assert {p["symbol"] for p in resp.json()} == {"0700.HK", "2800.HK", "9988.HK"}


def test_positions_filter_by_account(client: TestClient) -> None:
    resp = client.get("/api/v1/positions", params={"account_id": "schwab-IRA-4821"})
    assert {p["symbol"] for p in resp.json()} == {"VTI", "SCHD", "BND"}


def test_positions_unknown_filters_404(client: TestClient) -> None:
    assert client.get("/api/v1/positions", params={"group_id": "nope"}).status_code == 404
    assert client.get("/api/v1/positions", params={"account_id": "nope"}).status_code == 404


class _BrokenBroker(BrokerConnector):
    @property
    def info(self) -> Broker:
        return Broker(id="broken", name="Broken", is_simulated=True)

    async def get_accounts(self):
        raise ConnectionError("login expired")

    async def get_positions(self):
        return []


def test_failing_broker_does_not_break_portfolio(client: TestClient) -> None:
    service = PortfolioService(
        connectors=[mock_ibkr(), mock_futu(), _BrokenBroker()],
        groups=[],
        fx=StaticFxProvider(),
    )
    app.dependency_overrides[get_portfolio_service] = lambda: service
    try:
        data = client.get("/api/v1/portfolio").json()
    finally:
        app.dependency_overrides.clear()

    assert data["errors"] == [{"broker_id": "broken", "message": "login expired"}]
    assert {a["account"]["broker_id"] for a in data["accounts"]} == {"ibkr", "futu"}
