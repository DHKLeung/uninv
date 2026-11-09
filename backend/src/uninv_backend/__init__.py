"""uninv backend package.

`main()` is the console entry point declared in pyproject.toml, so
`uv run uninv-backend` starts the API server.
"""

import argparse

__version__ = "1.1.0"


def main() -> None:
    """Start the FastAPI server with uvicorn."""
    import uvicorn

    from uninv_backend.config import get_settings

    settings = get_settings()

    parser = argparse.ArgumentParser(prog="uninv-backend", description="Run the uninv API server.")
    parser.add_argument(
        "--host", default=settings.host, help="interface to bind (default: %(default)s)"
    )
    parser.add_argument(
        "--port", type=int, default=settings.port, help="port (default: %(default)s)"
    )
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (dev)")
    args = parser.parse_args()

    uvicorn.run(
        "uninv_backend.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
