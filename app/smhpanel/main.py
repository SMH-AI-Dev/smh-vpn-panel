"""FastAPI application factory."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import AppConfig, load_config
from .db import init_db, make_engine, make_session_factory
from .security import (
    CSRF_HEADER,
    SESSION_COOKIE,
    RateLimiter,
    decode_session_token,
)
from .services.helpers import HelperRunner
from .services.traffic import TrafficEngine
from .services.wireguard import WireGuardManager
from .services.xray_manager import XrayManager

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

AUTH_EXEMPT = {"/api/health", "/api/auth/login"}


def create_app(config: AppConfig | None = None) -> FastAPI:
    config = config or load_config()
    engine = make_engine(config.paths()["db"])
    init_db(engine)
    session_factory = make_session_factory(engine)

    runner = HelperRunner(config)
    manager = XrayManager(config, session_factory, runner)
    wg_manager = WireGuardManager(config, session_factory, runner)

    workers_enabled = (
        bool(config.get("runtime.workers", True))
        and os.environ.get("SMHPANEL_NO_WORKERS") != "1"
    )
    traffic = TrafficEngine(
        config,
        session_factory,
        runner,
        apply_cb=lambda: (manager.apply(), wg_manager.apply()),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if workers_enabled:
            await traffic.start()
        yield
        if workers_enabled:
            await traffic.stop()

    app = FastAPI(
        title="SMH Panel",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    app.state.config = config
    app.state.session_factory = session_factory
    app.state.runner = runner
    app.state.manager = manager
    app.state.wg_manager = wg_manager
    app.state.traffic = traffic
    app.state.rate_limiter = RateLimiter()

    @app.middleware("http")
    async def auth_guard(request: Request, call_next):
        path = request.url.path
        if path.startswith("/api/") and path not in AUTH_EXEMPT:
            token = request.cookies.get(SESSION_COOKIE)
            payload = decode_session_token(config.secret(), token) if token else None
            if not payload:
                return JSONResponse(
                    status_code=401, content={"detail": "authentication required"}
                )
            if (
                request.method not in ("GET", "HEAD", "OPTIONS")
                and path != "/api/auth/logout"
            ):
                csrf = request.headers.get(CSRF_HEADER)
                if not csrf or csrf != payload.get("csrf"):
                    return JSONResponse(
                        status_code=403, content={"detail": "invalid CSRF token"}
                    )
            request.state.admin = {
                "id": payload.get("sub"),
                "username": payload.get("username"),
            }
        return await call_next(request)

    from .api import auth, clients, inbounds, settings, sub, system_api

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__, "dev_mode": config.is_dev()}

    app.include_router(auth.router)
    app.include_router(inbounds.router)
    app.include_router(clients.router)
    app.include_router(settings.router)
    app.include_router(system_api.router)
    app.include_router(sub.router)

    if (STATIC_DIR / "assets").exists():
        app.mount(
            "/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets"
        )

    @app.get("/", include_in_schema=False)
    def index():
        target = STATIC_DIR / "index.html"
        if target.exists():
            return FileResponse(target)
        return JSONResponse(
            {"detail": "UI assets not installed"}, status_code=503
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith(("api/", "assets/", "sub/")):
            return JSONResponse(status_code=404, content={"detail": "not found"})
        candidate = STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        target = STATIC_DIR / "index.html"
        if target.exists():
            return FileResponse(target)
        return JSONResponse({"detail": "UI assets not installed"}, status_code=503)

    return app
