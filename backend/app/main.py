"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text

from app.config import Settings, get_settings
from app.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title="Career Radar", version="0.1.0")

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        database = "unconfigured"
        if settings.database_url:
            try:
                engine = create_engine(settings.database_url, pool_pre_ping=True)
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                database = "connected"
            except Exception:  # noqa: BLE001 - health must never raise
                database = "disconnected"
        return JSONResponse(
            {"status": "ok", "environment": settings.environment, "database": database}
        )

    return app


app = create_app()
