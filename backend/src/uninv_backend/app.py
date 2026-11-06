"""FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from uninv_backend import __version__
from uninv_backend.api.routes import router
from uninv_backend.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="uninv backend",
        version=__version__,
        description="Unified investing platform: broker connectors and portfolio aggregation.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(router)
    return app


app = create_app()
