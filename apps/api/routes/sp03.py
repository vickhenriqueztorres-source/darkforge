from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
import html
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.analytics.models import RetentionPolicy
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class AuthorizeYouTubeRequest(BaseModel):
    channel_id: UUID | None = None
    redirect_uri: str = "http://127.0.0.1:8000/api/v1/connections/youtube/callback"


class OAuthCallbackRequest(BaseModel):
    state: str = Field(min_length=8)
    code: str = Field(min_length=4)
    channel_id: UUID | None = None


class SyncChannelRequest(BaseModel):
    sync_scope: str = Field(default="catalog_incremental", pattern="^(catalog_incremental|catalog_backfill|analytics_daily)$")


def _serialize(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_serialize(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if hasattr(obj, "__dataclass_fields__"):
        return _serialize(asdict(obj))
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "value"):
        return obj.value
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def _require_analytics(container: ServiceContainer):
    if container.analytics is None:
        raise AppError(
            code=ErrorCode.SUPABASE_UNAVAILABLE,
            message="AnalyticsService requer DATABASE_URL e configuracao de servidor.",
            http_status=503,
            retryable=True,
        )
    return container.analytics


@router.post("/connections/youtube/authorize")
def authorize_youtube(
    body: AuthorizeYouTubeRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    return svc.start_youtube_oauth(actor, workspace_id, body.channel_id, body.redirect_uri)


@router.post("/connections/youtube/callback")
def youtube_callback(
    body: OAuthCallbackRequest,
    actor: AuthenticatedUser = Depends(get_current_user),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    conn = svc.handle_oauth_callback(actor, body.state, body.code, body.channel_id)
    return {"connection": _serialize(conn)}


@router.get("/connections/youtube/callback", response_class=HTMLResponse)
def youtube_browser_callback(
    state: str | None = Query(default=None),
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
    container: ServiceContainer = Depends(get_container),
) -> HTMLResponse:
    if error:
        msg = html.escape(error)
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#0a0d12;color:#f3f4f6;padding:32px'>"
            f"<h2>Autorização YouTube cancelada</h2><p>Erro retornado pelo Google: <code>{msg}</code></p>"
            f"<p><a href='http://127.0.0.1:3000/' style='color:#60a5fa'>Voltar ao DarkForge Studio</a></p></body></html>",
            status_code=400,
        )
    if not state or not code:
        return HTMLResponse(
            "<html><body style='font-family:sans-serif;background:#0a0d12;color:#f3f4f6;padding:32px'>"
            "<h2>Parâmetros OAuth ausentes</h2><p>State ou code não informado.</p></body></html>",
            status_code=400,
        )
    svc = _require_analytics(container)
    try:
        conn = svc.handle_oauth_browser_callback(state, code)
    except AppError as exc:
        return HTMLResponse(
            f"<html><body style='font-family:sans-serif;background:#0a0d12;color:#f3f4f6;padding:32px'>"
            f"<h2>Falha ao conectar YouTube</h2><p>{html.escape(exc.message)}</p>"
            f"<p><a href='http://127.0.0.1:3000/' style='color:#60a5fa'>Voltar ao DarkForge Studio</a></p></body></html>",
            status_code=exc.http_status,
        )
    ext_name = html.escape(conn.external_account_id or "Canal YouTube")
    return HTMLResponse(
        f"<html><body style='font-family:sans-serif;background:#0a0d12;color:#f3f4f6;padding:32px'>"
        f"<h2>Canal conectado com sucesso!</h2>"
        f"<p>Conta vinculada: <strong>{ext_name}</strong></p>"
        f"<p>Você pode fechar esta aba e clicar em <strong>Sincronizar Canal (Incremental)</strong> ou <strong>Atualizar</strong> no DarkForge Studio.</p>"
        f"<script>setTimeout(()=>window.close(), 1500);</script></body></html>"
    )


@router.get("/connections")
def list_connections(
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    return {"items": _serialize(svc.list_connections(actor, workspace_id))}


@router.delete("/connections/{connection_id}")
def disconnect_connection(
    connection_id: UUID,
    retention_policy: RetentionPolicy = Query(default=RetentionPolicy.KEEP_READONLY),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    return svc.disconnect_connection(actor, workspace_id, connection_id, retention_policy)


@router.post("/channels/{channel_id}/sync", status_code=202)
def sync_channel(
    channel_id: UUID,
    body: SyncChannelRequest | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    scope = body.sync_scope if body else "catalog_incremental"
    return svc.enqueue_channel_sync(actor, workspace_id, channel_id, sync_scope=scope, idempotency_key=idempotency_key)


@router.get("/analytics/portfolio")
def portfolio_analytics(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    e = end_date or (date.today() + timedelta(days=2))
    s = start_date or (e - timedelta(days=90))
    return _serialize(svc.get_portfolio_analytics(actor, workspace_id, s, e))


@router.get("/channels/{channel_id}/analytics")
def channel_analytics(
    channel_id: UUID,
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    e = end_date or (date.today() + timedelta(days=2))
    s = start_date or (e - timedelta(days=90))
    return _serialize(svc.get_channel_analytics(actor, workspace_id, channel_id, s, e))


@router.get("/videos/{video_id}")
def video_detail(
    video_id: UUID,
    actor: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_analytics(container)
    return _serialize(svc.get_video_detail(actor, workspace_id, video_id))
