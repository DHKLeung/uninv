# AGENTS.md: backend (Python / FastAPI)

Rules for `backend/`. Root `AGENTS.md` applies too.

## Layout
- `src/uninv_backend/models.py`: Pydantic models, **the API contract**. Changing a field
  here changes what the UI receives; update `desktop/src/js/*.js` to match.
- `brokers/base.py`: `BrokerConnector` ABC (async `info`, `get_accounts`, `get_positions`).
- `brokers/mock.py`: simulated brokers. `brokers/registry.py`: the active connector list
  (the only place to switch mock → real).
- `portfolio/service.py`: `PortfolioService`, which fetches all brokers concurrently and
  builds `PortfolioSummary`. `portfolio/groups.py`: hardcoded groups.
- `fx.py`: `FxProvider` protocol + `StaticFxProvider` (hardcoded rates).
- `api/routes.py`: `/api/v1` routes; `get_portfolio_service` is the DI hook (tests override
  it with `app.dependency_overrides`).
- `config.py`: `Settings` (env prefix `UNINV_`).

## Conventions
- Python 3.13, full type hints, `X | None`, `StrEnum`. Ruff: line length 100.
- Connectors convert broker data into the shared models; broker-specific types must not leak
  past `brokers/`.
- Broker I/O is async. If an SDK is sync-only, wrap it with `asyncio.to_thread`.
- One broker failing must not break the portfolio. Let exceptions surface from the connector;
  the service turns them into `PortfolioSummary.errors`.
- `Position.id = "<account_id>:<symbol>"` is how groups reference positions. Don't change
  the format without migrating the groups.
- Money is `float` for now (display only). Switch to `Decimal` before any accounting or tax
  features.
- Weights are fractions (0.12 = 12%); the UI formats them. Values ending in `_base` are in
  the base currency.
- Dependencies: `uv add <pkg>` / `uv add --dev <pkg>`; commit `uv.lock`. Keep runtime deps
  lean (the backend will be bundled with PyInstaller). Avoid `fastapi[standard]`, which pulls
  in cloud and telemetry extras.
- Tests live in `tests/`, use `fastapi.testclient.TestClient`, and assert invariants
  (weights sum to 1, totals add up) rather than hardcoded dollar amounts where possible.
