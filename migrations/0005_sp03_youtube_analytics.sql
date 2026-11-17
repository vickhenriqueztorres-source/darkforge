-- ============================================================================
-- Migration 0005: YouTube OAuth, Catalogo, Metricas, Cursor, QuotaLedger & RLS
-- Subplano: SP-03 (SP-03-T01..T10)
-- ADRs: ADR-004, ADR-005, ADR-009, ADR-011
-- ============================================================================

-- 1. OAuth PKCE/CSRF State (servidor/API apenas)
CREATE TABLE IF NOT EXISTS public.oauth_states (
    state text PRIMARY KEY,
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NULL REFERENCES public.channels(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    code_verifier text NOT NULL,
    redirect_uri text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

-- 2. Platform Connections (metadados visiveis na UI; segredos ficam isolados abaixo)
CREATE TABLE IF NOT EXISTS public.platform_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    platform text NOT NULL DEFAULT 'youtube' CHECK (platform IN ('youtube')),
    external_account_id text NULL,
    external_channel_id text NULL,
    scopes text[] NOT NULL DEFAULT ARRAY[]::text[],
    status text NOT NULL DEFAULT 'PENDING_AUTH' CHECK (
        status IN ('PENDING_AUTH', 'CONNECTED', 'TOKEN_EXPIRED', 'REVOKED_OR_INVALID', 'DISCONNECTED')
    ),
    token_expires_at timestamptz NULL,
    last_validated_at timestamptz NULL,
    last_error_code text NULL,
    last_error_message text NULL,
    retention_policy text NOT NULL DEFAULT 'keep_readonly',
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_connections_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE
);

CREATE TRIGGER trg_platform_connections_updated_at
    BEFORE UPDATE ON public.platform_connections
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 3. Segredos OAuth criptografados (NUNCA expostos ao navegador/authenticated)
CREATE TABLE IF NOT EXISTS public.platform_connection_secrets (
    connection_id uuid PRIMARY KEY REFERENCES public.platform_connections(id) ON DELETE CASCADE,
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    access_token_enc text NOT NULL,
    refresh_token_enc text NULL,
    key_version text NOT NULL DEFAULT 'aesgcm-v1',
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

-- 4. Videos e Playlists normalizados
CREATE TABLE IF NOT EXISTS public.videos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    platform text NOT NULL DEFAULT 'youtube' CHECK (platform IN ('youtube')),
    external_video_id text NOT NULL,
    canonical_url text NOT NULL,
    title text NOT NULL,
    description text NOT NULL DEFAULT '',
    format text NOT NULL DEFAULT 'long' CHECK (format IN ('long', 'short', 'live', 'unknown')),
    duration_seconds integer NULL CHECK (duration_seconds IS NULL OR duration_seconds >= 0),
    published_at timestamptz NULL,
    thumbnail_url text NULL,
    privacy_status text NOT NULL DEFAULT 'unknown',
    tags_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    source text NOT NULL DEFAULT 'youtube_data_api',
    source_updated_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, platform, external_video_id),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_videos_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_videos_ws_channel_pub
    ON public.videos (workspace_id, channel_id, published_at DESC);

CREATE TRIGGER trg_videos_updated_at
    BEFORE UPDATE ON public.videos
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

CREATE TABLE IF NOT EXISTS public.playlists (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    external_playlist_id text NOT NULL,
    title text NOT NULL,
    item_count integer NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, channel_id, external_playlist_id),
    CONSTRAINT fk_playlists_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE
);

-- 5. Catalogo versionado de metricas (SP-00-T05 / SP-03-T03)
CREATE TABLE IF NOT EXISTS public.metric_definitions (
    metric_id text PRIMARY KEY,
    catalog_version text NOT NULL DEFAULT 'v1',
    display_name text NOT NULL,
    visibility_scope text NOT NULL CHECK (visibility_scope IN ('private_authorized', 'public_snapshot')),
    source_api text NOT NULL,
    allowed_granularities text[] NOT NULL,
    allowed_dimensions text[] NOT NULL DEFAULT ARRAY['{}']::text[],
    supports_estimates boolean NOT NULL DEFAULT false,
    description text NOT NULL DEFAULT ''
);

INSERT INTO public.metric_definitions (metric_id, catalog_version, display_name, visibility_scope, source_api, allowed_granularities, allowed_dimensions)
VALUES
    ('yt.channel.subscribers_total', 'v1', 'Inscritos totais', 'private_authorized', 'youtube_data_api', ARRAY['snapshot'], ARRAY['{}']),
    ('yt.video.public_views', 'v1', 'Visualizacoes publicas', 'public_snapshot', 'youtube_data_api', ARRAY['snapshot'], ARRAY['{}']),
    ('yt.video.public_likes', 'v1', 'Likes publicos', 'public_snapshot', 'youtube_data_api', ARRAY['snapshot'], ARRAY['{}']),
    ('yt.video.public_comments', 'v1', 'Comentarios publicos', 'public_snapshot', 'youtube_data_api', ARRAY['snapshot'], ARRAY['{}']),
    ('yt.analytics.views', 'v1', 'Views consolidadas', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}', '{country}', '{traffic_source}']),
    ('yt.analytics.watch_time_minutes', 'v1', 'Tempo de exibicao (min)', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}', '{country}', '{traffic_source}']),
    ('yt.analytics.avg_view_duration_sec', 'v1', 'Duracao media (s)', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}']),
    ('yt.analytics.avg_view_percentage', 'v1', 'Percentual medio assistido', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}']),
    ('yt.analytics.subscribers_gained', 'v1', 'Inscritos ganhos', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}']),
    ('yt.analytics.subscribers_lost', 'v1', 'Inscritos perdidos', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}']),
    ('yt.analytics.impressions', 'v1', 'Impressoes', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}']),
    ('yt.analytics.impressions_ctr', 'v1', 'CTR de impressoes (%)', 'private_authorized', 'youtube_analytics_api', ARRAY['day', 'period_total'], ARRAY['{}']),
    ('yt.analytics.retention_curve', 'v1', 'Curva de retencao', 'private_authorized', 'youtube_analytics_api', ARRAY['curve_100'], ARRAY['{audience_type}']),
    ('yt.analytics.traffic_sources', 'v1', 'Fontes de trafego', 'private_authorized', 'youtube_analytics_api', ARRAY['period_total'], ARRAY['{traffic_source_type}'])
ON CONFLICT (metric_id) DO NOTHING;

-- 6. Fatos metricos (Snapshots e Series Temporais com revisoes e availability)
CREATE TABLE IF NOT EXISTS public.metric_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    video_id uuid NULL,
    metric_id text NOT NULL REFERENCES public.metric_definitions(metric_id),
    visibility_scope text NOT NULL CHECK (visibility_scope IN ('private_authorized', 'public_snapshot')),
    source text NOT NULL,
    source_revision integer NOT NULL DEFAULT 1 CHECK (source_revision >= 1),
    period_start date NOT NULL,
    period_end date NOT NULL,
    granularity text NOT NULL,
    dimensions_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    dimensions_hash text NOT NULL,
    availability text NOT NULL CHECK (availability IN ('available', 'unknown', 'delayed', 'partial', 'not_applicable')),
    value_num double precision NULL,
    is_estimate boolean NOT NULL DEFAULT false,
    fetched_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, channel_id, video_id, metric_id, period_start, period_end, granularity, dimensions_hash, source_revision),
    CONSTRAINT fk_metric_snapshots_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT chk_unavailable_has_null_value
        CHECK (availability = 'available' OR value_num IS NULL)
);

-- Indice unico funcional para video_id NULL vs NOT NULL (garante upsert idempotente)
CREATE UNIQUE INDEX IF NOT EXISTS uq_metric_snapshot_natural
    ON public.metric_snapshots (
        workspace_id,
        channel_id,
        COALESCE(video_id, '00000000-0000-0000-0000-000000000000'::uuid),
        metric_id,
        period_start,
        period_end,
        granularity,
        dimensions_hash,
        source_revision
    );

CREATE INDEX IF NOT EXISTS idx_metric_snapshots_lookup
    ON public.metric_snapshots (workspace_id, channel_id, metric_id, period_start, period_end, source_revision DESC);

-- 7. Sync Cursors (cursor transacional + frescor + erros parciais)
CREATE TABLE IF NOT EXISTS public.sync_cursors (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    connection_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    sync_scope text NOT NULL CHECK (sync_scope IN ('catalog_incremental', 'catalog_backfill', 'analytics_daily')),
    cursor_token text NULL,
    last_page_processed integer NOT NULL DEFAULT 0,
    last_successful_sync_at timestamptz NULL,
    source_updated_at timestamptz NULL,
    freshness_status text NOT NULL DEFAULT 'never_synced' CHECK (
        freshness_status IN ('fresh', 'stale', 'partial', 'blocked', 'never_synced')
    ),
    partial_errors_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, connection_id, sync_scope),
    CONSTRAINT fk_sync_cursors_conn_ws
        FOREIGN KEY (workspace_id, connection_id)
        REFERENCES public.platform_connections(workspace_id, id)
        ON DELETE CASCADE
);

CREATE TRIGGER trg_sync_cursors_updated_at
    BEFORE UPDATE ON public.sync_cursors
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 8. QuotaLedger (orcamento compartilhado do projeto YouTube API: own_sync > public_research)
CREATE TABLE IF NOT EXISTS public.quota_ledger (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    quota_date date NOT NULL DEFAULT (timezone('utc', now()))::date,
    pool text NOT NULL CHECK (pool IN ('own_sync', 'public_research')),
    operation text NOT NULL,
    reserved_units integer NOT NULL DEFAULT 0 CHECK (reserved_units >= 0),
    consumed_units integer NULL CHECK (consumed_units IS NULL OR consumed_units >= 0),
    status text NOT NULL DEFAULT 'RESERVED' CHECK (status IN ('RESERVED', 'COMMITTED', 'RELEASED', 'BLOCKED')),
    correlation_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_quota_ledger_day_pool
    ON public.quota_ledger (quota_date, pool, status);

-- 9. RLS & Grants SP-03
REVOKE ALL ON public.oauth_states FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.platform_connection_secrets FROM PUBLIC, anon, authenticated;
REVOKE ALL ON public.platform_connections FROM PUBLIC, anon;
REVOKE ALL ON public.videos FROM PUBLIC, anon;
REVOKE ALL ON public.playlists FROM PUBLIC, anon;
REVOKE ALL ON public.metric_definitions FROM PUBLIC, anon;
REVOKE ALL ON public.metric_snapshots FROM PUBLIC, anon;
REVOKE ALL ON public.sync_cursors FROM PUBLIC, anon;
REVOKE ALL ON public.quota_ledger FROM PUBLIC, anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.platform_connections TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.videos TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.playlists TO authenticated;
GRANT SELECT ON public.metric_definitions TO authenticated;
GRANT SELECT ON public.metric_snapshots TO authenticated;
GRANT SELECT ON public.sync_cursors TO authenticated;
GRANT SELECT ON public.quota_ledger TO authenticated;

ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.oauth_states FORCE ROW LEVEL SECURITY;
ALTER TABLE public.platform_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_connections FORCE ROW LEVEL SECURITY;
ALTER TABLE public.platform_connection_secrets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_connection_secrets FORCE ROW LEVEL SECURITY;
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.videos FORCE ROW LEVEL SECURITY;
ALTER TABLE public.playlists ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.playlists FORCE ROW LEVEL SECURITY;
ALTER TABLE public.metric_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.metric_definitions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.metric_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.metric_snapshots FORCE ROW LEVEL SECURITY;
ALTER TABLE public.sync_cursors ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sync_cursors FORCE ROW LEVEL SECURITY;
ALTER TABLE public.quota_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.quota_ledger FORCE ROW LEVEL SECURITY;

CREATE POLICY connections_select_member ON public.platform_connections
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY connections_write_editor ON public.platform_connections
    FOR ALL TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY videos_select_member ON public.videos
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY playlists_select_member ON public.playlists
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY metric_definitions_select_auth ON public.metric_definitions
    FOR SELECT TO authenticated USING (true);
CREATE POLICY metric_snapshots_select_member ON public.metric_snapshots
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY sync_cursors_select_member ON public.sync_cursors
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY quota_ledger_select_member ON public.quota_ledger
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
