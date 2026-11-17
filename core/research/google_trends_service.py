from __future__ import annotations

from typing import Any, Callable, Protocol
from uuid import UUID

from core.errors import AppError, ErrorCode
from core.research.google_trends_analyzer import evaluate_topic_sustainability
from core.research.google_trends_models import TrendsQueryItem, TrendsSeriesPoint
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


class GoogleTrendsCollectorPort(Protocol):
    def collect(self, *, keyword: str, geo: str = "BR", gprop: str = "youtube", hl: str = "pt-BR") -> dict[str, Any]: ...


class GoogleTrendsService:
    """Orchestrates Passo 4 Google Trends sustainability checks (12m, 5y, geo, Rising/Breakout) + 24h cache."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: Any,
        collector: GoogleTrendsCollectorPort | None = None,
        csv_timeline_parser: Callable[[str], list[TrendsSeriesPoint]] | None = None,
        csv_related_parser: Callable[[str], list[TrendsQueryItem]] | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._collector = collector
        self._parse_tl_csv = csv_timeline_parser
        self._parse_rq_csv = csv_related_parser

    def validate_keyword(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        keyword: str,
        *,
        channel_id: UUID | None = None,
        studio_term_id: UUID | None = None,
        geo: str | None = None,
        gprop: str = "youtube",
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        clean_kw = keyword.strip()
        if len(clean_kw) < 2:
            raise AppError(ErrorCode.VALIDATION_ERROR, "keyword deve ter ao menos 2 caracteres.", http_status=422)

        resolved_geo, resolved_hl = ("BR", "pt-BR")
        if channel_id:
            resolved_geo, resolved_hl = self._repo.get_channel_geo_lang(workspace_id, channel_id)
        final_geo = (geo or resolved_geo).strip().upper()

        if not force_refresh:
            cached = self._repo.find_cached_validation(workspace_id, clean_kw, final_geo, gprop)
            if cached is not None:
                return {"validation": cached, "cached": True}

        if self._collector is None:
            raise AppError(
                ErrorCode.STUDIO_RATE_LIMITED,
                "Coletor Google Trends nao configurado. Use Importacao CSV ou ative coleta assistida.",
                http_status=503,
            )

        raw = self._collector.collect(keyword=clean_kw, geo=final_geo, gprop=gprop, hl=resolved_hl)
        report = evaluate_topic_sustainability(
            keyword=clean_kw,
            geo=final_geo,
            gprop=gprop,
            points_12m=raw.get("points_12m", []),
            points_5y=raw.get("points_5y", []),
            related_queries=raw.get("related_queries", []),
        )
        saved = self._repo.save_validation(
            workspace_id=workspace_id,
            channel_id=channel_id,
            studio_term_id=studio_term_id,
            report=report,
            captured_via=str(raw.get("captured_via", "browser_json")),
            created_by=actor.user_id,
        )
        return {"validation": saved, "cached": False}

    def import_csv_validation(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        *,
        keyword: str,
        geo: str = "BR",
        gprop: str = "youtube",
        timeline_12m_csv: str = "",
        timeline_5y_csv: str = "",
        related_queries_csv: str = "",
        channel_id: UUID | None = None,
        studio_term_id: UUID | None = None,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        clean_kw = keyword.strip()
        if len(clean_kw) < 2:
            raise AppError(ErrorCode.VALIDATION_ERROR, "keyword obrigatorio.", http_status=422)
        if not self._parse_tl_csv or not self._parse_rq_csv:
            raise AppError(ErrorCode.VALIDATION_ERROR, "Parsers CSV nao configurados.", http_status=500)

        pts_12m = self._parse_tl_csv(timeline_12m_csv) if timeline_12m_csv.strip() else []
        pts_5y = self._parse_tl_csv(timeline_5y_csv) if timeline_5y_csv.strip() else []
        rel_q = self._parse_rq_csv(related_queries_csv) if related_queries_csv.strip() else []

        report = evaluate_topic_sustainability(
            keyword=clean_kw,
            geo=geo.strip().upper() or "BR",
            gprop=gprop,
            points_12m=pts_12m,
            points_5y=pts_5y,
            related_queries=rel_q,
        )
        saved = self._repo.save_validation(
            workspace_id=workspace_id,
            channel_id=channel_id,
            studio_term_id=studio_term_id,
            report=report,
            captured_via="csv_import",
            created_by=actor.user_id,
        )
        return {"validation": saved, "cached": False}

    def list_validations(self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None = None) -> list[dict[str, Any]]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_validations(workspace_id, channel_id=channel_id)
