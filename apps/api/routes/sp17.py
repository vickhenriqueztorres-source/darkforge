from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from apps.api.dependencies import (
    ServiceContainer,
    enforce_origin,
    get_container,
    get_current_user,
    get_workspace_id,
)
from core.errors import AppError, ErrorCode
from core.workspaces.models import AuthenticatedUser

router = APIRouter(prefix="/api/v1", dependencies=[Depends(enforce_origin)])


class ValidateGoogleTrendsRequest(BaseModel):
    keyword: str = Field(min_length=2, max_length=200)
    channel_id: UUID | None = None
    studio_term_id: UUID | None = None
    geo: str | None = Field(default=None, max_length=10)
    gprop: str = Field(default="youtube", pattern="^(youtube|web|news|images)$")
    force_refresh: bool = False


class ImportGoogleTrendsCsvRequest(BaseModel):
    keyword: str = Field(min_length=2, max_length=200)
    channel_id: UUID | None = None
    studio_term_id: UUID | None = None
    geo: str = Field(default="BR", max_length=10)
    gprop: str = Field(default="youtube", pattern="^(youtube|web|news|images)$")
    timeline_12m_csv: str = ""
    timeline_5y_csv: str = ""
    related_queries_csv: str = ""


def _ser(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_ser(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _ser(v) for k, v in obj.items()}
    if isinstance(obj, UUID):
        return str(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if hasattr(obj, "__float__") and type(obj).__name__ == "Decimal":
        return float(obj)
    return obj


def _require_gtrends(container: ServiceContainer):
    if container.google_trends is None:
        raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "GoogleTrendsService nao configurado.", http_status=503, retryable=True)
    return container.google_trends


@router.get("/research/google-trends")
def list_google_trends_validations(
    channel_id: UUID | None = Query(default=None),
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_gtrends(container)
    return _ser({"items": svc.list_validations(user, workspace_id, channel_id=channel_id)})


@router.post("/research/google-trends/validate")
def validate_google_trends(
    body: ValidateGoogleTrendsRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_gtrends(container)
    return _ser(
        svc.validate_keyword(
            user,
            workspace_id,
            body.keyword,
            channel_id=body.channel_id,
            studio_term_id=body.studio_term_id,
            geo=body.geo,
            gprop=body.gprop if body.gprop != "web" else "",
            force_refresh=body.force_refresh,
        )
    )


@router.post("/research/google-trends/import-csv")
def import_google_trends_csv(
    body: ImportGoogleTrendsCsvRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    workspace_id: UUID = Depends(get_workspace_id),
    container: ServiceContainer = Depends(get_container),
) -> dict[str, Any]:
    svc = _require_gtrends(container)
    return _ser(
        svc.import_csv_validation(
            user,
            workspace_id,
            keyword=body.keyword,
            geo=body.geo,
            gprop=body.gprop if body.gprop != "web" else "",
            timeline_12m_csv=body.timeline_12m_csv,
            timeline_5y_csv=body.timeline_5y_csv,
            related_queries_csv=body.related_queries_csv,
            channel_id=body.channel_id,
            studio_term_id=body.studio_term_id,
        )
    )
