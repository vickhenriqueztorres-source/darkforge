from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any
from uuid import UUID

from core.analytics.models import (
    AnalyticsBatchResult,
    CatalogPageResult,
    MetricFactInput,
    MetricFactView,
    OAuthTokenBundle,
    PlatformConnection,
    QuotaPool,
    RetentionPolicy,
    SyncCursorView,
    VideoRecord,
)


class YouTubePlatformPort(ABC):
    @abstractmethod
    def build_authorize_url(self, state: str, code_challenge: str, redirect_uri: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> OAuthTokenBundle:
        raise NotImplementedError

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> OAuthTokenBundle:
        raise NotImplementedError

    @abstractmethod
    def revoke_token(self, token: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def fetch_own_channel_and_videos_page(
        self, access_token: str, page_token: str | None = None, max_results: int = 25
    ) -> CatalogPageResult:
        raise NotImplementedError

    @abstractmethod
    def fetch_channel_analytics(
        self,
        access_token: str,
        external_channel_id: str,
        start_date: date,
        end_date: date,
        external_video_ids: list[str],
    ) -> AnalyticsBatchResult:
        raise NotImplementedError


class AnalyticsRepositoryPort(ABC):
    @abstractmethod
    def save_oauth_state(
        self, state: str, workspace_id: UUID, channel_id: UUID | None, user_id: UUID, code_verifier: str, redirect_uri: str
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def consume_oauth_state(self, state: str) -> tuple[UUID, UUID | None, UUID, str, str] | None:
        raise NotImplementedError

    @abstractmethod
    def create_or_update_connection(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        user_id: UUID,
        tokens: OAuthTokenBundle,
        external_channel_id: str | None = None,
    ) -> PlatformConnection:
        raise NotImplementedError

    @abstractmethod
    def get_connection(self, workspace_id: UUID, connection_id: UUID) -> PlatformConnection | None:
        raise NotImplementedError

    @abstractmethod
    def get_connection_for_channel(self, workspace_id: UUID, channel_id: UUID) -> PlatformConnection | None:
        raise NotImplementedError

    @abstractmethod
    def list_connections(self, workspace_id: UUID) -> list[PlatformConnection]:
        raise NotImplementedError

    @abstractmethod
    def get_decrypted_tokens(self, workspace_id: UUID, connection_id: UUID) -> OAuthTokenBundle:
        raise NotImplementedError

    @abstractmethod
    def mark_connection_status(
        self, workspace_id: UUID, connection_id: UUID, status: str, error_code: str | None = None, error_message: str | None = None
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def disconnect_connection(
        self, workspace_id: UUID, connection_id: UUID, retention_policy: RetentionPolicy
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def reserve_quota(
        self, workspace_id: UUID, pool: QuotaPool, operation: str, estimated_units: int, correlation_id: UUID
    ) -> UUID:
        raise NotImplementedError

    @abstractmethod
    def commit_quota(self, reservation_id: UUID, actual_units: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def release_quota(self, reservation_id: UUID) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_quota_summary(self, workspace_id: UUID) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_sync_cursor(self, workspace_id: UUID, connection_id: UUID, sync_scope: str) -> SyncCursorView | None:
        raise NotImplementedError

    @abstractmethod
    def commit_sync_unit(
        self,
        workspace_id: UUID,
        connection_id: UUID,
        channel_id: UUID,
        sync_scope: str,
        next_cursor_token: str | None,
        page_number: int,
        videos: list[dict[str, Any]],
        facts: list[MetricFactInput],
        freshness_status: str,
        partial_errors: list[dict[str, Any]],
    ) -> dict[str, int]:
        """Commits videos, facts (with revision history), and sync cursor atomically."""
        raise NotImplementedError

    @abstractmethod
    def list_videos(self, workspace_id: UUID, channel_id: UUID, limit: int = 50, offset: int = 0) -> list[VideoRecord]:
        raise NotImplementedError

    @abstractmethod
    def get_video_detail(self, workspace_id: UUID, video_id: UUID) -> tuple[VideoRecord, list[MetricFactView]] | None:
        raise NotImplementedError

    @abstractmethod
    def get_channel_analytics(
        self, workspace_id: UUID, channel_id: UUID, start_date: date, end_date: date
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_portfolio_analytics(self, workspace_id: UUID, start_date: date, end_date: date) -> list[dict[str, Any]]:
        raise NotImplementedError
