-- ============================================================================
-- Migration 0011: YouTube Studio Trends Scraper & Outlier Engine (SP-10..SP-14)
-- ADR: ADR-017 (Automacao assistida com Human-in-the-Loop)
-- ============================================================================

-- 1. Allow evidence_links to trace Studio Trends terms & outlier videos
ALTER TABLE public.evidence_links
    DROP CONSTRAINT IF EXISTS evidence_links_source_kind_check;

ALTER TABLE public.evidence_links
    ADD CONSTRAINT evidence_links_source_kind_check CHECK (
        source_kind IN (
            'channel_profile',
            'analytics_fact',
            'reference_video',
            'knowledge_chunk',
            'title_analysis',
            'thumbnail_analysis',
            'studio_trend_term',
            'studio_outlier_video'
        )
    );

-- 2. Studio Trend Runs
CREATE TABLE IF NOT EXISTS public.studio_trend_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    broad_topic text NOT NULL CHECK (char_length(trim(broad_topic)) BETWEEN 2 AND 200),
    filters_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'QUEUED' CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'BLOCKED', 'FAILED')
    ),
    captured_via text NOT NULL DEFAULT 'hybrid',
    error_code text NULL,
    error_message text NULL,
    limitations_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    job_id uuid NULL,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_studio_runs_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id) ON DELETE CASCADE
);

CREATE TRIGGER trg_studio_trend_runs_updated_at
    BEFORE UPDATE ON public.studio_trend_runs
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 3. Studio Search Terms (Top Searches + Content Gaps como hipoteses)
CREATE TABLE IF NOT EXISTS public.studio_search_terms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    term text NOT NULL CHECK (char_length(trim(term)) >= 1),
    block_type text NOT NULL CHECK (block_type IN ('top_search', 'content_gap')),
    audience_interest text NOT NULL DEFAULT 'medium' CHECK (
        audience_interest IN ('unknown', 'low', 'medium', 'high', 'very_high')
    ),
    is_hypothesis boolean NOT NULL DEFAULT false,
    gap_note text NOT NULL DEFAULT '',
    weekly_views_gt_1000 boolean NOT NULL DEFAULT true,
    curation_status text NOT NULL DEFAULT 'pending' CHECK (
        curation_status IN ('pending', 'approved', 'rejected', 'archived')
    ),
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    FOREIGN KEY (workspace_id, run_id)
        REFERENCES public.studio_trend_runs(workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_studio_terms_ws_ch
    ON public.studio_search_terms (workspace_id, channel_id, block_type, audience_interest);

-- 4. Studio Video Outliers (3x, 5x+ media/mediana do canal)
CREATE TABLE IF NOT EXISTS public.studio_video_outliers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    external_video_id text NOT NULL,
    canonical_url text NOT NULL,
    title text NOT NULL,
    external_channel_id text NULL,
    channel_name text NOT NULL DEFAULT '',
    public_views bigint NULL,
    channel_baseline_views double precision NULL,
    outlier_ratio double precision NULL,
    outlier_tier text NOT NULL DEFAULT 'insufficient_baseline',
    baseline_sample_size integer NOT NULL DEFAULT 0,
    watched_by_my_viewers boolean NOT NULL DEFAULT false,
    published_days_ago integer NULL,
    source_origin text NOT NULL DEFAULT 'youtube_studio_trends_browser',
    curation_status text NOT NULL DEFAULT 'pending' CHECK (
        curation_status IN ('pending', 'approved', 'rejected', 'archived')
    ),
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, run_id, external_video_id),
    FOREIGN KEY (workspace_id, run_id)
        REFERENCES public.studio_trend_runs(workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_studio_outliers_ws_ratio
    ON public.studio_video_outliers (workspace_id, channel_id, outlier_ratio DESC NULLS LAST);

-- 5. RLS & Permissoes
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'studio_trend_runs',
        'studio_search_terms',
        'studio_video_outliers'
    ]
    LOOP
        EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY;', tbl);
        EXECUTE format('REVOKE ALL ON public.%I FROM PUBLIC, anon;', tbl);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON public.%I TO authenticated;', tbl);
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));',
            'p_' || tbl || '_select', tbl
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR INSERT TO authenticated WITH CHECK (app.has_workspace_role(workspace_id, ARRAY[''owner'',''editor'']));',
            'p_' || tbl || '_insert', tbl
        );
        EXECUTE format(
            'CREATE POLICY %I ON public.%I FOR UPDATE TO authenticated USING (app.has_workspace_role(workspace_id, ARRAY[''owner'',''editor''])) WITH CHECK (app.has_workspace_role(workspace_id, ARRAY[''owner'',''editor'']));',
            'p_' || tbl || '_update', tbl
        );
    END LOOP;
END
$$;
