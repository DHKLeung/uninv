# uninv-backend

Python FastAPI service for uninv. It talks to the brokers and combines their data into one
portfolio. The desktop app reads from it over HTTP on `127.0.0.1`.

See the [root README](../README.md) for the full architecture.

## Commands

Run all of these from the `backend/` directory:

```powershell
uv sync                      # create .venv and install dependencies
uv run uninv-backend         # start the API on http://127.0.0.1:8000 (auto-reload)
uv run pytest                # run the tests
uv run ruff check .          # lint
uv run ruff format .         # format
```

Once the server is up, the interactive API docs are at <http://127.0.0.1:8000/docs>.

## Layout

```text
src/uninv_backend/
├── __init__.py        # main(): entry point used by `uv run uninv-backend`
├── app.py             # FastAPI app factory (CORS, routers)
├── config.py          # settings (env vars prefixed with UNINV_)
├── models.py          # Pydantic models: Account, Position, Group, PortfolioSummary...
├── fx.py              # currency conversion (hardcoded rates for now)
├── api/
│   └── routes.py      # HTTP endpoints under /api/v1
├── brokers/
│   ├── base.py        # BrokerConnector: the interface every broker implements
│   ├── mock.py        # simulated brokers that return hardcoded positions
│   └── registry.py    # which connectors are active
└── portfolio/
    ├── groups.py      # user-defined position groups (hardcoded for now)
    └── service.py     # combines data from all brokers into the unified portfolio
```

## Adding a real broker

1. Create `brokers/<name>.py` with a class that subclasses `BrokerConnector`. It needs to
   implement `get_accounts()` and `get_positions()` and return the shared models.
2. Register it in `brokers/registry.py`.
3. Nothing else should need to change. The aggregation code, the API and the desktop app only
   use the shared models.
