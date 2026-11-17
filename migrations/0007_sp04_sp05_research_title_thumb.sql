-- ============================================================================
-- Migration 0007: Research Explorer (SP-04) & Title/Thumbnail Intel (SP-05)
-- ADRs: ADR-005, ADR-009, ADR-011
-- ============================================================================

-- 1. Research Runs (SP-04-T01)
CREATE TABLE IF NOT EXISTS public.research_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    objective text NOT NULL,
    query_terms text[] NOT NULL DEFAULT ARRAY[]::text[],
    language text NOT NULL DEFAULT 'pt-BR',
    period_days integer NOT NULL DEFAULT 90 CHECK (period_days BETWEEN 1 AND 3650),
    format_filter text NOT NULL DEFAULT 'all' CHECK (format_filter IN ('all', 'long', 'short', 'live')),
    quota_budget integer NOT NULL DEFAULT 50 CHECK (quota_budget >= 1),
    quota_consumed integer NOT NULL DEFAULT 0,
    algorithm_version text NOT NULL DEFAULT 'sim-v1',
    idempotency_key text NOT NULL,
    status text NOT NULL DEFAULT 'QUEUED' CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'BLOCKED', 'FAILED')),
    limitations_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, idempotency_key),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_research_runs_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE
);

CREATE TRIGGER trg_research_runs_updated_at
    BEFORE UPDATE ON public.research_runs
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 2. Reference Channels & Videos (dados publicos auditaveis; NUNCA analytics privado)
CREATE TABLE IF NOT EXISTS public.reference_channels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    research_run_id uuid NULL,
    platform text NOT NULL DEFAULT 'youtube' CHECK (platform IN ('youtube')),
    external_channel_id text NOT NULL,
    canonical_url text NOT NULL,
    display_name text NOT NULL,
    language text NULL,
    similarity_score double precision NOT NULL DEFAULT 0 CHECK (similarity_score BETWEEN 0 AND 100),
    similarity_factors_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    curation_status text NOT NULL DEFAULT 'pending' CHECK (curation_status IN ('pending', 'approved', 'rejected', 'archived')),
    collection_name text NOT NULL DEFAULT 'default',
    notes text NOT NULL DEFAULT '',
    source_origin text NOT NULL DEFAULT 'youtube_public_data_api',
    observed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, platform, external_channel_id),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_ref_channels_run_ws
        FOREIGN KEY (workspace_id, research_run_id)
        REFERENCES public.research_runs(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ref_channels_ws_curation
    ON public.reference_channels (workspace_id, curation_status, similarity_score DESC);

CREATE TRIGGER trg_reference_channels_updated_at
    BEFORE UPDATE ON public.reference_channels
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

CREATE TABLE IF NOT EXISTS public.reference_videos (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    reference_channel_id uuid NULL,
    research_run_id uuid NULL,
    platform text NOT NULL DEFAULT 'youtube' CHECK (platform IN ('youtube')),
    external_video_id text NOT NULL,
    canonical_url text NOT NULL,
    content_hash text NOT NULL,
    title text NOT NULL,
    description text NOT NULL DEFAULT '',
    format text NOT NULL DEFAULT 'unknown',
    duration_seconds integer NULL,
    published_at timestamptz NULL,
    thumbnail_url text NULL,
    public_views_snapshot bigint NULL,
    public_likes_snapshot bigint NULL,
    public_comments_snapshot bigint NULL,
    curation_status text NOT NULL DEFAULT 'pending' CHECK (curation_status IN ('pending', 'approved', 'rejected', 'archived')),
    collection_name text NOT NULL DEFAULT 'default',
    notes text NOT NULL DEFAULT '',
    source_origin text NOT NULL DEFAULT 'youtube_public_data_api',
    snapshot_observed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, platform, external_video_id),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_ref_videos_ch_ws
        FOREIGN KEY (workspace_id, reference_channel_id)
        REFERENCES public.reference_channels(workspace_id, id)
        ON DELETE SET NULL,
    CONSTRAINT fk_ref_videos_run_ws
        FOREIGN KEY (workspace_id, research_run_id)
        REFERENCES public.research_runs(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_ref_videos_ws_curation
    ON public.reference_videos (workspace_id, curation_status, snapshot_observed_at DESC);

CREATE TRIGGER trg_reference_videos_updated_at
    BEFORE UPDATE ON public.reference_videos
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 3. Title Analyses & Thumbnail Assets/Analyses (SP-05)
CREATE TABLE IF NOT EXISTS public.title_analyses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NULL,
    reference_video_id uuid NULL,
    source_title text NOT NULL,
    analyzer_version text NOT NULL DEFAULT 'title-struct-v1',
    features_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    editorial_formula text NOT NULL DEFAULT '',
    confidence double precision NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    limitations_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_title_analyses_ref_ws
        FOREIGN KEY (workspace_id, reference_video_id)
        REFERENCES public.reference_videos(workspace_id, id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS public.thumbnail_assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    reference_video_id uuid NULL,
    source_url text NOT NULL,
    sha256 text NULL,
    rights_status text NOT NULL DEFAULT 'reference_only' CHECK (rights_status IN ('reference_only', 'owned', 'licensed', 'restricted')),
    retention_until timestamptz NULL,
    availability_status text NOT NULL DEFAULT 'available' CHECK (availability_status IN ('available', 'unavailable', 'blocked')),
    collected_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, source_url),
    UNIQUE (workspace_id, id)
);

CREATE TABLE IF NOT EXISTS public.thumbnail_analyses (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    thumbnail_asset_id uuid NOT NULL,
    vision_status text NOT NULL CHECK (vision_status IN ('available', 'unavailable')),
    ocr_text text NULL,
    composition_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    differentiation_notes text NOT NULL DEFAULT '',
    is_probabilistic boolean NOT NULL DEFAULT true,
    limitations_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_thumb_analyses_asset_ws
        FOREIGN KEY (workspace_id, thumbnail_asset_id)
        REFERENCES public.thumbnail_assets(workspace_id, id)
        ON DELETE CASCADE
);

-- 4. RLS & Grants SP-04 / SP-05
REVOKE ALL ON public.research_runs FROM PUBLIC, anon;
REVOKE ALL ON public.reference_channels FROM PUBLIC, anon;
REVOKE ALL ON public.reference_videos FROM PUBLIC, anon;
REVOKE ALL ON public.title_analyses FROM PUBLIC, anon;
REVOKE ALL ON public.thumbnail_assets FROM PUBLIC, anon;
REVOKE ALL ON public.thumbnail_analyses FROM PUBLIC, anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.research_runs TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.reference_channels TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.reference_videos TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.title_analyses TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.thumbnail_assets TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.thumbnail_analyses TO authenticated;

ALTER TABLE public.research_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.research_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.reference_channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reference_channels FORCE ROW LEVEL SECURITY;
ALTER TABLE public.reference_videos ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reference_videos FORCE ROW LEVEL SECURITY;
ALTER TABLE public.title_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.title_analyses FORCE ROW LEVEL SECURITY;
ALTER TABLE public.thumbnail_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.thumbnail_assets FORCE ROW LEVEL SECURITY;
ALTER TABLE public.thumbnail_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.thumbnail_analyses FORCE ROW LEVEL SECURITY;

CREATE POLICY research_runs_member ON public.research_runs
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY ref_channels_member ON public.reference_channels
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY ref_videos_member ON public.reference_videos
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY title_analyses_member ON public.title_analyses
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY thumbnail_assets_member ON public.thumbnail_assets
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY thumbnail_analyses_member ON public.thumbnail_analyses
    FOR ALL TO authenticated
    USING (app.is_workspace_member(workspace_id))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));
