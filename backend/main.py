"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.routers import health, sessions, uploads
from backend.config import get_settings
from backend.db.base import engine, Base

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Agentic Research Assistant API",
        description=(
            "Multi-Agent LLM-RAG Framework for Autonomous Scientific "
            "Literature Mining, Research Gap Discovery, and Knowledge Synthesis."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Request size limit (50 MB) ────────────────────────────────────────────
    from starlette.middleware.base import BaseHTTPMiddleware

    class LimitUploadSizeMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > settings.max_upload_size_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"error": "Request too large", "detail": f"Max {settings.max_upload_size_mb} MB"},
                )
            return await call_next(request)

    app.add_middleware(LimitUploadSizeMiddleware)

    # ── Global exception handler (no stack traces in responses) ───────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": None},
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    PREFIX = "/api/v1"
    app.include_router(health.router, prefix=PREFIX)
    app.include_router(sessions.router, prefix=PREFIX)
    app.include_router(uploads.router, prefix=PREFIX)

    # ── Startup ───────────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logger.info("Starting Agentic Research Assistant API...")
        settings.ensure_data_dirs()
        # Auto-create all tables (dev convenience; Alembic handles prod)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables ensured.")

    @app.on_event("shutdown")
    async def on_shutdown():
        await engine.dispose()
        logger.info("Database engine disposed.")

    return app


app = create_app()
