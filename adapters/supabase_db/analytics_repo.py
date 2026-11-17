from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from adapters.youtube.token_vault import TokenVault
from core.analytics.models import (
    ConnectionStatus,
    MetricAvailability,
    MetricFactInput,
    MetricFactView,
    OAuthTokenBundle,
    PlatformConnection,
    QuotaPool,
    RetentionPolicy,
    SyncCursorView,
    VideoRecord,
    canonical_dimensions_hash,
)
from core.analytics.ports import AnalyticsRepositoryPort
from core.errors import AppError, ErrorCode


class PostgresAnalyticsRepository(AnalyticsRepositoryPort):
    """Postgres repository for OAuth connections, atomic sync cursors, quota ledger, and analytics."""

    def __init__(
        self,
        database_url: str,
        vault: TokenVault,
        daily_quota_limit: int = 10000,
        own_sync_reserved_units: int = 4000,
    ) -> None:
        self._dsn = database_url
        self._vault = vault
        self._daily_quota_limit = daily_quota_limit
        self._own_sync_reserved = own_sync_reserved_units

    def _connect(self) -> psycopg.Connection[Any]:
        try:
            return psycopg.connect(self._dsn, connect_timeout=6, row_factory=dict_row)
        except psycopg.Error as exc:
            raise AppError(ErrorCode.SUPABASE_UNAVAILABLE, "Postgres indisponivel.", http_status=503, retryable=True) from exc

    def save_oauth_state(
        self, state: str, workspace_id: UUID, channel_id: UUID | None, user_id: UUID, code_verifier: str, redirect_uri: str
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO public.oauth_states (state, workspace_id, channel_id, user_id, code_verifier, redirect_uri, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, timezone('utc', now()) + interval '15 minutes')
                """,
                (state, str(workspace_id), str(channel_id) if channel_id else None, str(user_id), code_verifier, redirect_uri),
            )
            conn.commit()

    def consume_oauth_state(self, state: str) -> tuple[UUID, UUID | None, UUID, str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                UPDATE public.oauth_states
                SET consumed_at = timezone('utc', now())
                WHERE state = %s AND consumed_at IS NULL AND expires_at > timezone('utc', now())
                RETURNING workspace_id, channel_id, user_id, code_verifier, redirect_uri
                """,
                (state,),
            ).fetchone()
            conn.commit()
        if not row:
            return None
        return (
            UUID(str(row["workspace_id"])),
            UUID(str(row["channel_id"])) if row.get("channel_id") else None,
            UUID(str(row["user_id"])),
            row["code_verifier"],
            row["redirect_uri"],
        )

    def create_or_update_connection(
        self,
        workspace_id: UUID,
        channel_id: UUID,
        user_id: UUID,
        tokens: OAuthTokenBundle,
        external_channel_id: str | None = None,
    ) -> PlatformConnection:
        access_enc = self._vault.encrypt(tokens.access_token)
        refresh_enc = self._vault.encrypt(tokens.refresh_token) if tokens.refresh_token else None

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM public.platform_connections WHERE workspace_id = %s AND channel_id = %s LIMIT 1",
                (str(workspace_id), str(channel_id)),
            ).fetchone()

            if existing:
                row = conn.execute(
                    """
                    UPDATE public.platform_connections
                    SET status = 'CONNECTED',
                        scopes = %s,
                        external_account_id = COALESCE(%s, external_account_id),
                        external_channel_id = COALESCE(%s, external_channel_id),
                        token_expires_at = %s,
                        last_validated_at = timezone('utc', now()),
                        last_error_code = NULL,
                        last_error_message = NULL
                    WHERE id = %s AND workspace_id = %s
                    RETURNING *
                    """,
                    (tokens.scopes, tokens.external_account_id, external_channel_id, tokens.expires_at, str(existing["id"]), str(workspace_id)),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    INSERT INTO public.platform_connections
                        (workspace_id, channel_id, platform, external_account_id, external_channel_id, scopes, status, token_expires_at, last_validated_at, created_by)
                    VALUES (%s, %s, 'youtube', %s, %s, %s, 'CONNECTED', %s, timezone('utc', now()), %s)
                    RETURNING *
                    """,
                    (str(workspace_id), str(channel_id), tokens.external_account_id, external_channel_id, tokens.scopes, tokens.expires_at, str(user_id)),
                ).fetchone()

            conn.execute(
                """
                INSERT INTO public.platform_connection_secrets (connection_id, workspace_id, access_token_enc, refresh_token_enc)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (connection_id) DO UPDATE
                SET access_token_enc = EXCLUDED.access_token_enc,
                    refresh_token_enc = COALESCE(EXCLUDED.refresh_token_enc, public.platform_connection_secrets.refresh_token_enc),
                    updated_at = timezone('utc', now())
                """,
                (str(row["id"]), str(workspace_id), access_enc, refresh_enc),
            )
            conn.commit()
        return self._to_connection(row)

    def get_connection(self, workspace_id: UUID, connection_id: UUID) -> PlatformConnection | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM public.platform_connections WHERE workspace_id = %s AND id = %s",
                (str(workspace_id), str(connection_id)),
            ).fetchone()
        return self._to_connection(row) if row else None

    def get_connection_for_channel(self, workspace_id: UUID, channel_id: UUID) -> PlatformConnection | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM public.platform_connections WHERE workspace_id = %s AND channel_id = %s ORDER BY created_at DESC LIMIT 1",
                (str(workspace_id), str(channel_id)),
            ).fetchone()
        return self._to_connection(row) if row else None

    def list_connections(self, workspace_id: UUID) -> list[PlatformConnection]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM public.platform_connections WHERE workspace_id = %s ORDER BY created_at DESC",
                (str(workspace_id),),
            ).fetchall()
        return [self._to_connection(r) for r in rows]

    def get_decrypted_tokens(self, workspace_id: UUID, connection_id: UUID) -> OAuthTokenBundle:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT pc.scopes, pc.token_expires_at, pc.external_account_id, s.access_token_enc, s.refresh_token_enc
                FROM public.platform_connections AS pc
                JOIN public.platform_connection_secrets AS s ON s.connection_id = pc.id
                WHERE pc.workspace_id = %s AND pc.id = %s
                """,
                (str(workspace_id), str(connection_id)),
            ).fetchone()
        if not row:
            raise AppError(ErrorCode.OAUTH_REQUIRED_OR_REVOKED, "Segredos OAuth ausentes; reconecte o canal.", http_status=401)
        return OAuthTokenBundle(
            access_token=self._vault.decrypt(row["access_token_enc"]),
            refresh_token=self._vault.decrypt(row["refresh_token_enc"]) if row.get("refresh_token_enc") else None,
            expires_at=row["token_expires_at"] or datetime.now(timezone.utc),
            scopes=list(row["scopes"] or []),
            external_account_id=row.get("external_account_id"),
        )

    def mark_connection_status(
        self, workspace_id: UUID, connection_id: UUID, status: str, error_code: str | None = None, error_message: str | None = None
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE public.platform_connections
                SET status = %s, last_error_code = %s, last_error_message = %s
                WHERE workspace_id = %s AND id = %s
                """,
                (status, error_code, error_message, str(workspace_id), str(connection_id)),
            )
            conn.commit()

    def disconnect_connection(
        self, workspace_id: UUID, connection_id: UUID, retention_policy: RetentionPolicy
    ) -> dict[str, Any]:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM public.platform_connection_secrets WHERE workspace_id = %s AND connection_id = %s",
                (str(workspace_id), str(connection_id)),
            )
            conn.execute(
                """
                UPDATE public.platform_connections
                SET status = 'DISCONNECTED', retention_policy = %s, last_error_code = NULL, last_error_message = NULL
                WHERE workspace_id = %s AND id = %s
                """,
                (retention_policy.value, str(workspace_id), str(connection_id)),
            )
            purged_videos = 0
            if retention_policy == RetentionPolicy.PURGE_SYNCED_DATA:
                row = conn.execute(
                    "SELECT channel_id FROM public.platform_connections WHERE id = %s AND workspace_id = %s",
                    (str(connection_id), str(workspace_id)),
                ).fetchone()
                if row:
                    ch_id = str(row["channel_id"])
                    conn.execute("DELETE FROM public.metric_snapshots WHERE workspace_id = %s AND channel_id = %s", (str(workspace_id), ch_id))
                    res = conn.execute("DELETE FROM public.videos WHERE workspace_id = %s AND channel_id = %s", (str(workspace_id), ch_id))
                    purged_videos = res.rowcount or 0
            conn.commit()
        return {
            "connection_id": str(connection_id),
            "status": "DISCONNECTED",
            "retention_policy": retention_policy.value,
            "tokens_deleted": True,
            "purged_videos": purged_videos,
        }

    def reserve_quota(
        self, workspace_id: UUID, pool: QuotaPool, operation: str, estimated_units: int, correlation_id: UUID
    ) -> UUID:
        today = date.today()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COALESCE(SUM(COALESCE(consumed_units, reserved_units)), 0) AS total_used,
                    COALESCE(SUM(COALESCE(consumed_units, reserved_units)) FILTER (WHERE pool = 'public_research'), 0) AS research_used
                FROM public.quota_ledger
                WHERE quota_date = %s AND status IN ('RESERVED', 'COMMITTED')
                """,
                (today,),
            ).fetchone()
            total_used = int(row["total_used"]) if row else 0
            research_used = int(row["research_used"]) if row else 0
            research_ceiling = max(0, self._daily_quota_limit - self._own_sync_reserved)
            over_total = total_used + estimated_units > self._daily_quota_limit
            over_research = pool == QuotaPool.PUBLIC_RESEARCH and (research_used + estimated_units > research_ceiling)
            if over_total or over_research:
                conn.execute(
                    """
                    INSERT INTO public.quota_ledger (workspace_id, quota_date, pool, operation, reserved_units, consumed_units, status, correlation_id)
                    VALUES (%s, %s, %s, %s, %s, 0, 'BLOCKED', %s)
                    """,
                    (str(workspace_id), today, pool.value, operation, estimated_units, str(correlation_id)),
                )
                conn.commit()
                raise AppError(
                    code=ErrorCode.YOUTUBE_QUOTA_EXCEEDED,
                    message=f"Orcamento de quota esgotado para pool={pool.value}.",
                    http_status=429,
                    retryable=True,
                )

            ins = conn.execute(
                """
                INSERT INTO public.quota_ledger (workspace_id, quota_date, pool, operation, reserved_units, status, correlation_id)
                VALUES (%s, %s, %s, %s, %s, 'RESERVED', %s)
                RETURNING id
                """,
                (str(workspace_id), today, pool.value, operation, estimated_units, str(correlation_id)),
            ).fetchone()
            conn.commit()
        return UUID(str(ins["id"]))

    def commit_quota(self, reservation_id: UUID, actual_units: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE public.quota_ledger SET status = 'COMMITTED', consumed_units = %s WHERE id = %s",
                (actual_units, str(reservation_id)),
            )
            conn.commit()

    def release_quota(self, reservation_id: UUID) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE public.quota_ledger SET status = 'RELEASED', consumed_units = 0 WHERE id = %s AND status = 'RESERVED'",
                (str(reservation_id),),
            )
            conn.commit()

    def get_quota_summary(self, workspace_id: UUID) -> dict[str, Any]:
        today = date.today()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT pool, COALESCE(SUM(COALESCE(consumed_units, reserved_units)), 0) AS used
                FROM public.quota_ledger
                WHERE quota_date = %s AND status IN ('RESERVED', 'COMMITTED')
                GROUP BY pool
                """,
                (today,),
            ).fetchall()
        by_pool = {r["pool"]: int(r["used"]) for r in rows}
        return {
            "quota_date": today.isoformat(),
            "daily_limit": self._daily_quota_limit,
            "own_sync_reserved": self._own_sync_reserved,
            "own_sync_used": by_pool.get("own_sync", 0),
            "public_research_used": by_pool.get("public_research", 0),
        }

    def get_sync_cursor(self, workspace_id: UUID, connection_id: UUID, sync_scope: str) -> SyncCursorView | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM public.sync_cursors
                WHERE workspace_id = %s AND connection_id = %s AND sync_scope = %s
                """,
                (str(workspace_id), str(connection_id), sync_scope),
            ).fetchone()
        if not row:
            return None
        return SyncCursorView(
            sync_scope=row["sync_scope"],
            freshness_status=row["freshness_status"],
            last_page_processed=int(row["last_page_processed"]),
            last_successful_sync_at=row.get("last_successful_sync_at"),
            source_updated_at=row.get("source_updated_at"),
            cursor_token=row.get("cursor_token"),
            partial_errors=list(row.get("partial_errors_json") or []),
        )

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
        """Atomic single-transaction commit of videos, revised facts, and cursor (T-YT-002 / AN-007)."""
        now = datetime.now(timezone.utc)
        videos_upserted = 0
        facts_recorded = 0

        with self._connect() as conn:
            video_id_map: dict[str, UUID] = {}
            for v in videos:
                row = conn.execute(
                    """
                    INSERT INTO public.videos (
                        workspace_id, channel_id, platform, external_video_id, canonical_url,
                        title, description, format, duration_seconds, published_at, thumbnail_url,
                        privacy_status, tags_json, source, source_updated_at
                    )
                    VALUES (%s, %s, 'youtube', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'youtube_data_api', %s)
                    ON CONFLICT (workspace_id, platform, external_video_id) DO UPDATE
                    SET title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        format = EXCLUDED.format,
                        duration_seconds = EXCLUDED.duration_seconds,
                        thumbnail_url = EXCLUDED.thumbnail_url,
                        privacy_status = EXCLUDED.privacy_status,
                        tags_json = EXCLUDED.tags_json,
                        source_updated_at = EXCLUDED.source_updated_at
                    RETURNING id
                    """,
                    (
                        str(workspace_id),
                        str(channel_id),
                        v["external_video_id"],
                        v["canonical_url"],
                        v["title"],
                        v.get("description", ""),
                        v.get("format", "unknown"),
                        v.get("duration_seconds"),
                        v.get("published_at"),
                        v.get("thumbnail_url"),
                        v.get("privacy_status", "unknown"),
                        json.dumps(v.get("tags_json") or []),
                        now,
                    ),
                ).fetchone()
                vid_uuid = UUID(str(row["id"]))
                video_id_map[v["external_video_id"]] = vid_uuid
                videos_upserted += 1

                # Record public video statistics snapshots cleanly (missing -> unknown, never 0)
                stats = v.get("statistics") or {}
                today = date.today()
                for stat_key, metric_id in (
                    ("viewCount", "yt.video.public_views"),
                    ("likeCount", "yt.video.public_likes"),
                    ("commentCount", "yt.video.public_comments"),
                ):
                    raw_val = stats.get(stat_key)
                    avail = MetricAvailability.AVAILABLE if raw_val is not None else MetricAvailability.UNKNOWN
                    val_num = float(raw_val) if raw_val is not None else None
                    facts.append(
                        MetricFactInput(
                            metric_id=metric_id,
                            visibility_scope="public_snapshot",
                            source="youtube_data_api",
                            period_start=today,
                            period_end=today,
                            granularity="snapshot",
                            dimensions_json={},
                            availability=avail,
                            value_num=val_num,
                            external_video_id=v["external_video_id"],
                        )
                    )

            for f in facts:
                vid_uuid = video_id_map.get(f.external_video_id) if f.external_video_id else None
                dim_hash = canonical_dimensions_hash(f.dimensions_json)
                existing_rev = conn.execute(
                    """
                    SELECT source_revision, availability, value_num
                    FROM public.metric_snapshots
                    WHERE workspace_id = %s
                      AND channel_id = %s
                      AND COALESCE(video_id, '00000000-0000-0000-0000-000000000000'::uuid) = COALESCE(%s::uuid, '00000000-0000-0000-0000-000000000000'::uuid)
                      AND metric_id = %s
                      AND period_start = %s
                      AND period_end = %s
                      AND granularity = %s
                      AND dimensions_hash = %s
                    ORDER BY source_revision DESC
                    LIMIT 1
                    """,
                    (
                        str(workspace_id),
                        str(channel_id),
                        str(vid_uuid) if vid_uuid else None,
                        f.metric_id,
                        f.period_start,
                        f.period_end,
                        f.granularity,
                        dim_hash,
                    ),
                ).fetchone()

                if existing_rev is not None:
                    same_val = existing_rev["value_num"] == f.value_num and existing_rev["availability"] == f.availability.value
                    if same_val:
                        continue  # Idempotent retry does not create duplicate revision
                    next_rev = int(existing_rev["source_revision"]) + 1
                else:
                    next_rev = 1

                conn.execute(
                    """
                    INSERT INTO public.metric_snapshots (
                        workspace_id, channel_id, video_id, metric_id, visibility_scope, source,
                        source_revision, period_start, period_end, granularity, dimensions_json,
                        dimensions_hash, availability, value_num, is_estimate, fetched_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(workspace_id),
                        str(channel_id),
                        str(vid_uuid) if vid_uuid else None,
                        f.metric_id,
                        f.visibility_scope,
                        f.source,
                        next_rev,
                        f.period_start,
                        f.period_end,
                        f.granularity,
                        json.dumps(f.dimensions_json),
                        dim_hash,
                        f.availability.value,
                        f.value_num,
                        f.is_estimate,
                        now,
                    ),
                )
                facts_recorded += 1

            conn.execute(
                """
                INSERT INTO public.sync_cursors (
                    workspace_id, connection_id, channel_id, sync_scope, cursor_token,
                    last_page_processed, last_successful_sync_at, source_updated_at, freshness_status, partial_errors_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (workspace_id, connection_id, sync_scope) DO UPDATE
                SET cursor_token = EXCLUDED.cursor_token,
                    last_page_processed = EXCLUDED.last_page_processed,
                    last_successful_sync_at = EXCLUDED.last_successful_sync_at,
                    source_updated_at = EXCLUDED.source_updated_at,
                    freshness_status = EXCLUDED.freshness_status,
                    partial_errors_json = EXCLUDED.partial_errors_json
                """,
                (
                    str(workspace_id),
                    str(connection_id),
                    str(channel_id),
                    sync_scope,
                    next_cursor_token,
                    page_number,
                    now,
                    now,
                    freshness_status,
                    json.dumps(partial_errors),
                ),
            )
            conn.commit()
        return {"videos_upserted": videos_upserted, "facts_recorded": facts_recorded}

    def list_videos(self, workspace_id: UUID, channel_id: UUID, limit: int = 50, offset: int = 0) -> list[VideoRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM public.videos
                WHERE workspace_id = %s AND channel_id = %s
                ORDER BY published_at DESC NULLS LAST, created_at DESC
                LIMIT %s OFFSET %s
                """,
                (str(workspace_id), str(channel_id), limit, offset),
            ).fetchall()
        return [self._to_video(r) for r in rows]

    def get_video_detail(self, workspace_id: UUID, video_id: UUID) -> tuple[VideoRecord, list[MetricFactView]] | None:
        with self._connect() as conn:
            v_row = conn.execute(
                "SELECT * FROM public.videos WHERE workspace_id = %s AND id = %s",
                (str(workspace_id), str(video_id)),
            ).fetchone()
            if not v_row:
                return None
            m_rows = conn.execute(
                """
                SELECT ms.*, md.display_name
                FROM public.metric_snapshots AS ms
                JOIN public.metric_definitions AS md ON md.metric_id = ms.metric_id
                WHERE ms.workspace_id = %s AND ms.video_id = %s
                ORDER BY ms.metric_id ASC, ms.source_revision DESC
                """,
                (str(workspace_id), str(video_id)),
            ).fetchall()
        return self._to_video(v_row), [self._to_fact_view(m) for m in m_rows]

    def get_channel_analytics(
        self, workspace_id: UUID, channel_id: UUID, start_date: date, end_date: date
    ) -> dict[str, Any]:
        with self._connect() as conn:
            m_rows = conn.execute(
                """
                SELECT DISTINCT ON (ms.metric_id, ms.granularity, ms.dimensions_hash)
                    ms.*, md.display_name
                FROM public.metric_snapshots AS ms
                JOIN public.metric_definitions AS md ON md.metric_id = ms.metric_id
                WHERE ms.workspace_id = %s
                  AND ms.channel_id = %s
                  AND ms.video_id IS NULL
                  AND ms.period_end >= %s
                  AND ms.period_start <= %s
                ORDER BY ms.metric_id, ms.granularity, ms.dimensions_hash, ms.source_revision DESC
                """,
                (str(workspace_id), str(channel_id), start_date, end_date),
            ).fetchall()
            cursors = conn.execute(
                "SELECT * FROM public.sync_cursors WHERE workspace_id = %s AND channel_id = %s",
                (str(workspace_id), str(channel_id)),
            ).fetchall()
            videos = self.list_videos(workspace_id, channel_id, limit=50, offset=0)

        return {
            "channel_id": str(channel_id),
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
            "metrics": [self._to_fact_view(m) for m in m_rows],
            "cursors": [
                SyncCursorView(
                    sync_scope=c["sync_scope"],
                    freshness_status=c["freshness_status"],
                    last_page_processed=int(c["last_page_processed"]),
                    last_successful_sync_at=c.get("last_successful_sync_at"),
                    source_updated_at=c.get("source_updated_at"),
                    partial_errors=list(c.get("partial_errors_json") or []),
                )
                for c in cursors
            ],
            "videos": videos,
        }

    def get_portfolio_analytics(self, workspace_id: UUID, start_date: date, end_date: date) -> list[dict[str, Any]]:
        with self._connect() as conn:
            ch_rows = conn.execute(
                "SELECT id, display_name, handle, status FROM public.channels WHERE workspace_id = %s ORDER BY created_at DESC",
                (str(workspace_id),),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for ch in ch_rows:
            data = self.get_channel_analytics(workspace_id, UUID(str(ch["id"])), start_date, end_date)
            items.append(
                {
                    "channel_id": str(ch["id"]),
                    "display_name": ch["display_name"],
                    "handle": ch.get("handle"),
                    "metrics": data["metrics"],
                    "cursors": data["cursors"],
                    "video_count": len(data["videos"]),
                }
            )
        return items

    @staticmethod
    def _to_connection(r: dict[str, Any]) -> PlatformConnection:
        return PlatformConnection(
            id=UUID(str(r["id"])),
            workspace_id=UUID(str(r["workspace_id"])),
            channel_id=UUID(str(r["channel_id"])),
            platform=r["platform"],
            status=ConnectionStatus(r["status"]),
            scopes=list(r.get("scopes") or []),
            external_account_id=r.get("external_account_id"),
            external_channel_id=r.get("external_channel_id"),
            token_expires_at=r.get("token_expires_at"),
            last_validated_at=r.get("last_validated_at"),
            last_error_code=r.get("last_error_code"),
            last_error_message=r.get("last_error_message"),
            retention_policy=r.get("retention_policy", "keep_readonly"),
        )

    @staticmethod
    def _to_video(r: dict[str, Any]) -> VideoRecord:
        return VideoRecord(
            id=UUID(str(r["id"])),
            workspace_id=UUID(str(r["workspace_id"])),
            channel_id=UUID(str(r["channel_id"])),
            external_video_id=r["external_video_id"],
            canonical_url=r["canonical_url"],
            title=r["title"],
            description=r.get("description", ""),
            format=r.get("format", "unknown"),
            duration_seconds=r.get("duration_seconds"),
            published_at=r.get("published_at"),
            thumbnail_url=r.get("thumbnail_url"),
            privacy_status=r.get("privacy_status", "unknown"),
            source=r.get("source", "youtube_data_api"),
            source_updated_at=r.get("source_updated_at"),
        )

    @staticmethod
    def _to_fact_view(r: dict[str, Any]) -> MetricFactView:
        return MetricFactView(
            id=UUID(str(r["id"])),
            metric_id=r["metric_id"],
            display_name=r.get("display_name", r["metric_id"]),
            visibility_scope=r["visibility_scope"],
            source=r["source"],
            source_revision=int(r["source_revision"]),
            period_start=r["period_start"],
            period_end=r["period_end"],
            granularity=r["granularity"],
            dimensions_json=r.get("dimensions_json") or {},
            availability=MetricAvailability(r["availability"]),
            value_num=r.get("value_num"),
            is_estimate=bool(r.get("is_estimate", False)),
            fetched_at=r["fetched_at"],
            video_id=UUID(str(r["video_id"])) if r.get("video_id") else None,
        )
