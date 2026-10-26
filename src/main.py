"""FastAPI application factory, usable by the server and isolated tests."""
from fastapi import FastAPI

from src.config import Settings
from src.routers.ask import router as ask_router
from src.routers.ping import router as health_router
from src.routers.search import router as search_router


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="PaperLens API",
        version="0.4.0",
        description="Day 4: keyword retrieval over stored research-paper records.",
    )
    app.state.settings = settings if settings is not None else Settings()
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(ask_router, prefix="/api/v1")
    app.include_router(search_router, prefix="/api/v1")
    return app
