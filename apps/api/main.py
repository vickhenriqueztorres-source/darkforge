from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.config import Settings, get_settings
from apps.api.dependencies import ServiceContainer, build_default_container
from apps.api.routes.sp01 import router as sp01_router
from apps.api.routes.sp02 import router as sp02_router
from apps.api.routes.sp03 import router as sp03_router
from apps.api.routes.sp04_sp05 import router as sp04_sp05_router
from apps.api.routes.sp06 import router as sp06_router
from apps.api.routes.sp07 import router as sp07_router
from apps.api.routes.sp08 import router as sp08_router
from apps.api.routes.sp09 import router as sp09_router
from apps.api.routes.sp13 import router as sp13_router
from apps.api.routes.sp17 import router as sp17_router
from apps.api.routes.sp22 import router as sp22_router
from apps.api.routes.sp24 import router as sp24_router
from apps.api.routes.studio import router as studio_router
from apps.api.routes.youtube_public import router as youtube_public_router
from core.errors import AppError


def create_app(
    settings: Settings | None = None,
    container: ServiceContainer | None = None,
) -> FastAPI:
    cfg = settings or get_settings()
    app = FastAPI(title="DarkForge Channel OS API", version="0.1.0")
    app.state.container = container or build_default_container(cfg)

    allowed_origins = [cfg.web_origin, "http://127.0.0.1:3000", "http://localhost:3000"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys(allowed_origins)),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Workspace-Id", "Idempotency-Key", "X-Correlation-Id"],
    )

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        corr = request.headers.get("X-Correlation-Id")
        payload = exc.to_envelope()
        if corr:
            payload["correlation_id"] = corr
        else:
            payload["correlation_id"] = payload.get("correlation_id") or str(uuid4())
        return JSONResponse(status_code=exc.http_status, content=payload)

    app.include_router(sp01_router)
    app.include_router(sp02_router)
    app.include_router(sp03_router)
    app.include_router(sp04_sp05_router)
    app.include_router(sp06_router)
    app.include_router(sp07_router)
    app.include_router(sp08_router)
    app.include_router(sp09_router)
    app.include_router(sp13_router)
    app.include_router(sp17_router)
    app.include_router(sp22_router)
    app.include_router(sp24_router)
    app.include_router(studio_router)
    app.include_router(youtube_public_router)
    return app


app = create_app()
