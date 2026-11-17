from __future__ import annotations

import base64
import hashlib
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from core.analytics.catalog import assert_compatible_comparison, validate_metric_fact_spec
from core.analytics.models import (
    ConnectionStatus,
    MetricFactView,
    PlatformConnection,
    QuotaPool,
    RetentionPolicy,
)
from core.analytics.ports import AnalyticsRepositoryPort, YouTubePlatformPort
from core.errors import AppError, ErrorCode
from core.jobs.service import CommandBus
from core.workspaces.models import AuthenticatedUser, WorkspaceRole
from core.workspaces.service import WorkspaceService


class AnalyticsService:
    """Manages YouTube OAuth connections, quota ledger, sync, and honest analytics (SP-03)."""

    def __init__(
        self,
        workspaces: WorkspaceService,
        repo: AnalyticsRepositoryPort,
        youtube: YouTubePlatformPort,
        command_bus: CommandBus | None = None,
    ) -> None:
        self._workspaces = workspaces
        self._repo = repo
        self._yt = youtube
        self._bus = command_bus

    def start_youtube_oauth(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID | None, redirect_uri: str
    ) -> dict[str, str]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        state = base64.urlsafe_b64encode(os.urandom(24)).decode("ascii").rstrip("=")
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("=")
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

        self._repo.save_oauth_state(state, workspace_id, channel_id, actor.user_id, code_verifier, redirect_uri)
        auth_url = self._yt.build_authorize_url(state=state, code_challenge=code_challenge, redirect_uri=redirect_uri)
        return {"authorize_url": auth_url, "state": state}

    def _complete_oauth_exchange(
        self,
        workspace_id: UUID,
        channel_id: UUID | None,
        user_id: UUID,
        code: str,
        code_verifier: str,
        redirect_uri: str,
    ) -> PlatformConnection:
        if channel_id is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "channel_id obrigatorio para vincular conexao YouTube.", http_status=422)
        bundle = self._yt.exchange_code(code, code_verifier, redirect_uri)
        return self._repo.create_or_update_connection(workspace_id, channel_id, user_id, bundle)

    def handle_oauth_callback(
        self, actor: AuthenticatedUser, state: str, code: str, target_channel_id: UUID | None = None
    ) -> PlatformConnection:
        consumed = self._repo.consume_oauth_state(state)
        if consumed is None:
            raise AppError(
                code=ErrorCode.OAUTH_REQUIRED_OR_REVOKED,
                message="State OAuth invalido, expirado ou ja utilizado.",
                http_status=401,
            )
        workspace_id, stored_channel_id, state_user_id, code_verifier, redirect_uri = consumed
        if state_user_id != actor.user_id:
            raise AppError(ErrorCode.WORKSPACE_FORBIDDEN, "Callback OAuth nao pertence ao usuario autenticado.", http_status=403)
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        return self._complete_oauth_exchange(
            workspace_id,
            target_channel_id or stored_channel_id,
            actor.user_id,
            code,
            code_verifier,
            redirect_uri,
        )

    def handle_oauth_browser_callback(self, state: str, code: str) -> PlatformConnection:
        """Completes PKCE OAuth exchange from Google browser GET redirect using one-time server state."""
        consumed = self._repo.consume_oauth_state(state)
        if consumed is None:
            raise AppError(
                code=ErrorCode.OAUTH_REQUIRED_OR_REVOKED,
                message="State OAuth invalido, expirado ou ja utilizado.",
                http_status=401,
            )
        workspace_id, stored_channel_id, state_user_id, code_verifier, redirect_uri = consumed
        return self._complete_oauth_exchange(
            workspace_id,
            stored_channel_id,
            state_user_id,
            code,
            code_verifier,
            redirect_uri,
        )

    def list_connections(self, actor: AuthenticatedUser, workspace_id: UUID) -> list[PlatformConnection]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.list_connections(workspace_id)

    def disconnect_connection(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        connection_id: UUID,
        retention_policy: RetentionPolicy,
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id, (WorkspaceRole.OWNER, WorkspaceRole.EDITOR))
        conn = self._repo.get_connection(workspace_id, connection_id)
        if conn is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Conexao nao encontrada neste workspace.", http_status=404)
        try:
            tokens = self._repo.get_decrypted_tokens(workspace_id, connection_id)
            self._yt.revoke_token(tokens.refresh_token or tokens.access_token)
        except AppError:
            pass  # Local disconnection proceeds even if remote token already expired/revoked
        return self._repo.disconnect_connection(workspace_id, connection_id, retention_policy)

    def enqueue_channel_sync(
        self,
        actor: AuthenticatedUser,
        workspace_id: UUID,
        channel_id: UUID,
        sync_scope: str = "catalog_incremental",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        if self._bus is None:
            raise AppError(ErrorCode.VALIDATION_ERROR, "CommandBus nao configurado.", http_status=500)
        conn = self._repo.get_connection_for_channel(workspace_id, channel_id)
        if conn is None or conn.status in (ConnectionStatus.DISCONNECTED, ConnectionStatus.REVOKED_OR_INVALID):
            raise AppError(
                code=ErrorCode.OAUTH_REQUIRED_OR_REVOKED,
                message="Canal sem conexao OAuth ativa. Autorize antes de sincronizar.",
                http_status=401,
                details={"next_action": "Conecte o canal via YouTube OAuth."},
            )
        job, deduplicated = self._bus.dispatch_job_command(
            actor=actor,
            workspace_id=workspace_id,
            channel_id=channel_id,
            job_type="youtube.channel_sync",
            idempotency_key=idempotency_key or f"sync-{channel_id}-{sync_scope}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}",
            payload_json={"channel_id": str(channel_id), "connection_id": str(conn.id), "sync_scope": sync_scope},
            total_steps=2,
            priority=80,  # Own-channel sync prioritizes over research
        )
        return {"job_id": str(job.id), "status": job.status.value, "deduplicated": deduplicated}

    def execute_sync_unit(
        self,
        workspace_id: UUID,
        connection_id: UUID,
        channel_id: UUID,
        sync_scope: str = "catalog_incremental",
        max_pages: int = 2,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict[str, Any]:
        """Executes OAuth check/refresh + HTTP fetch outside DB txn, then commits cursor+facts atomically."""
        conn = self._repo.get_connection(workspace_id, connection_id)
        if conn is None or conn.status == ConnectionStatus.DISCONNECTED:
            raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Conexao desconectada.", http_status=401)

        tokens = self._repo.get_decrypted_tokens(workspace_id, connection_id)
        if tokens.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=2):
            if not tokens.refresh_token:
                self._repo.mark_connection_status(
                    workspace_id, connection_id, ConnectionStatus.TOKEN_EXPIRED.value, "OAUTH_REQUIRED_OR_REVOKED", "Refresh token ausente."
                )
                raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Token expirado e sem refresh token.", http_status=401)
            try:
                refreshed = self._yt.refresh_access_token(tokens.refresh_token)
                self._repo.create_or_update_connection(workspace_id, channel_id, conn.created_by if hasattr(conn, "created_by") else workspace_id, refreshed, conn.external_channel_id)  # type: ignore[attr-defined]
                tokens = refreshed
            except AppError as err:
                self._repo.mark_connection_status(
                    workspace_id, connection_id, ConnectionStatus.REVOKED_OR_INVALID.value, err.code.value, err.message
                )
                raise

        cursor = self._repo.get_sync_cursor(workspace_id, connection_id, sync_scope)
        page_token: str | None = cursor.cursor_token if cursor else None
        pages_done = cursor.last_page_processed if cursor else 0
        total_videos = 0
        total_facts = 0
        all_errors: list[dict[str, Any]] = []
        ext_channel_id = conn.external_channel_id or ""
        ext_video_ids: list[str] = []

        for _ in range(max_pages):
            res_id = self._repo.reserve_quota(workspace_id, QuotaPool.OWN_SYNC, "youtube.catalog_page", 5, uuid4())
            try:
                page = self._yt.fetch_own_channel_and_videos_page(tokens.access_token, page_token=page_token)
                self._repo.commit_quota(res_id, page.quota_cost)
            except Exception:
                self._repo.release_quota(res_id)
                raise

            ext_channel_id = page.external_channel_id or ext_channel_id
            for v in page.videos:
                if v.get("external_video_id"):
                    ext_video_ids.append(v["external_video_id"])

            pages_done += 1
            stats = self._repo.commit_sync_unit(
                workspace_id=workspace_id,
                connection_id=connection_id,
                channel_id=channel_id,
                sync_scope=sync_scope,
                next_cursor_token=page.next_page_token,
                page_number=pages_done,
                videos=page.videos,
                facts=[],
                freshness_status="fresh" if page.next_page_token is None else "partial",
                partial_errors=[],
            )
            total_videos += stats.get("videos_upserted", 0)
            page_token = page.next_page_token
            if page_token is None:
                break

        # Fetch channel & video analytics outside DB transaction
        s_date = start_date or (date.today() - timedelta(days=28))
        e_date = end_date or date.today()
        res_id = self._repo.reserve_quota(workspace_id, QuotaPool.OWN_SYNC, "youtube.analytics_batch", 10, uuid4())
        try:
            batch = self._yt.fetch_channel_analytics(tokens.access_token, ext_channel_id, s_date, e_date, ext_video_ids)
            self._repo.commit_quota(res_id, batch.quota_cost)
        except Exception:
            self._repo.release_quota(res_id)
            raise

        for fact in batch.facts:
            validate_metric_fact_spec(fact.metric_id, fact.granularity, fact.dimensions_json, fact.visibility_scope)
        all_errors.extend(batch.partial_errors)

        freshness = "partial" if all_errors else "fresh"
        stats_a = self._repo.commit_sync_unit(
            workspace_id=workspace_id,
            connection_id=connection_id,
            channel_id=channel_id,
            sync_scope="analytics_daily",
            next_cursor_token=None,
            page_number=1,
            videos=[],
            facts=batch.facts,
            freshness_status=freshness,
            partial_errors=all_errors,
        )
        total_facts += stats_a.get("facts_recorded", 0)
        return {
            "videos_upserted": total_videos,
            "facts_recorded": total_facts,
            "freshness_status": freshness,
            "partial_errors": all_errors,
        }

    def get_portfolio_analytics(
        self, actor: AuthenticatedUser, workspace_id: UUID, start_date: date, end_date: date
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        items = self._repo.get_portfolio_analytics(workspace_id, start_date, end_date)
        quota = self._repo.get_quota_summary(workspace_id)
        return {"period_start": start_date.isoformat(), "period_end": end_date.isoformat(), "channels": items, "quota": quota}

    def get_channel_analytics(
        self, actor: AuthenticatedUser, workspace_id: UUID, channel_id: UUID, start_date: date, end_date: date
    ) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        return self._repo.get_channel_analytics(workspace_id, channel_id, start_date, end_date)

    def get_video_detail(self, actor: AuthenticatedUser, workspace_id: UUID, video_id: UUID) -> dict[str, Any]:
        self._workspaces.require_membership(actor, workspace_id)
        res = self._repo.get_video_detail(workspace_id, video_id)
        if res is None:
            raise AppError(ErrorCode.RESOURCE_NOT_FOUND, "Video nao encontrado neste workspace.", http_status=404)
        video, facts = res
        return {"video": video, "metrics": facts}

    @staticmethod
    def compare_facts(facts: list[MetricFactView]) -> dict[str, Any]:
        assert_compatible_comparison(facts)
        return {"compatible": True, "count": len(facts), "items": facts}
