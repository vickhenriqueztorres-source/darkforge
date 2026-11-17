-- ============================================================================
-- Migration 0012: Google Trends Sustainability Validation (SP-15..SP-18)
-- ============================================================================

-- 1. Extend evidence_links to cite Google Trends validations
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
            'studio_outlier_video',
            'google_trends_validation'
        )
    );

-- 2. Google Trends Validations (12m, 5y, Region/Language, Rising & Breakout)
CREATE TABLE IF NOT EXISTS public.google_trends_validations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NULL,
    studio_term_id uuid NULL,
    keyword text NOT NULL CHECK (char_length(trim(keyword)) >= 1),
    geo text NOT NULL DEFAULT 'BR',
    gprop text NOT NULL DEFAULT 'youtube',
    direction_12m text NOT NULL DEFAULT 'insufficient',
    recent_avg_12m double precision NOT NULL DEFAULT 0,
    baseline_avg_12m double precision NOT NULL DEFAULT 0,
    slope_12m double precision NOT NULL DEFAULT 0,
    durability_5y text NOT NULL DEFAULT 'insufficient',
    peak_decay_pct double precision NOT NULL DEFAULT 0,
    seasonal_months_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    verdict text NOT NULL CHECK (
        verdict IN ('SUSTAINABLE_GO', 'SEASONAL_TIMING', 'CAUTION_DECLINING', 'AVOID_DEAD_PEAK', 'INSUFFICIENT_DATA')
    ),
    confidence numeric(5,4) NOT NULL DEFAULT 0,
    summary text NOT NULL DEFAULT '',
    points_12m_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    points_5y_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    top_queries_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    rising_queries_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    breakout_queries_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    limitations_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    captured_via text NOT NULL DEFAULT 'playwright_json',
    status text NOT NULL DEFAULT 'SUCCEEDED' CHECK (status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'BLOCKED', 'FAILED')),
    job_id uuid NULL,
    expires_at timestamptz NOT NULL DEFAULT (timezone('utc', now()) + interval '24 hours'),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_gtrends_lookup
    ON public.google_trends_validations (workspace_id, lower(keyword), geo, gprop, expires_at DESC);

ALTER TABLE public.google_trends_validations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.google_trends_validations FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.google_trends_validations FROM PUBLIC, anon;
GRANT SELECT, INSERT, UPDATE ON public.google_trends_validations TO authenticated;

CREATE POLICY p_google_trends_validations_select ON public.google_trends_validations
    FOR SELECT TO authenticated
    USING (app.is_workspace_member(workspace_id));

CREATE POLICY p_google_trends_validations_insert ON public.google_trends_validations
    FOR INSERT TO authenticated
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY p_google_trends_validations_update ON public.google_trends_validations
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));
