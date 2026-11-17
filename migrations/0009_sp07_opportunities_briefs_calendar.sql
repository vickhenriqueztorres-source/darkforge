-- ============================================================================
-- Migration 0009: Opportunity Engine, Episode Briefs, Feedback & Calendar
-- Subplano: SP-07 (OPP-001..006, EDIT-001..006, T-ED-001)
-- ADRs: ADR-007, ADR-008, ADR-009, ADR-011
-- ============================================================================

-- 1. Opportunities
CREATE TABLE IF NOT EXISTS public.opportunities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    profile_version_id uuid NULL,
    theme text NOT NULL CHECK (char_length(trim(theme)) BETWEEN 2 AND 240),
    angle text NOT NULL CHECK (char_length(trim(angle)) >= 2),
    target_format text NOT NULL DEFAULT 'long' CHECK (target_format IN ('long', 'short', 'live')),
    differentiation text NOT NULL,
    score numeric(5,4) NOT NULL CHECK (score >= 0 AND score <= 1),
    score_version text NOT NULL DEFAULT 'v1.0.0',
    score_breakdown_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    confidence numeric(5,4) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    limitations_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    data_freshness text NOT NULL DEFAULT 'fresh',
    insufficient_data boolean NOT NULL DEFAULT false,
    analyst_reports_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'GENERATED' CHECK (
        status IN ('GENERATED', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'ARCHIVED')
    ),
    created_by uuid NOT NULL,
    reviewed_by uuid NULL,
    reviewed_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id),
    FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_opportunities_workspace_status
    ON public.opportunities (workspace_id, channel_id, status, score DESC);

CREATE TRIGGER trg_opportunities_updated_at
    BEFORE UPDATE ON public.opportunities
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 2. Evidence Links (referencias rastreaveis entre oportunidade/brief e fontes)
CREATE TABLE IF NOT EXISTS public.evidence_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    entity_type text NOT NULL CHECK (entity_type IN ('opportunity', 'episode_brief', 'generation')),
    entity_id uuid NOT NULL,
    source_kind text NOT NULL CHECK (
        source_kind IN ('channel_profile', 'analytics_fact', 'reference_video', 'knowledge_chunk', 'title_analysis', 'thumbnail_analysis')
    ),
    source_id text NOT NULL,
    snippet text NOT NULL DEFAULT '',
    source_url text NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_evidence_links_entity
    ON public.evidence_links (workspace_id, entity_type, entity_id);

-- 3. Opportunity Feedback (OPP-004/005 - sem alegar fine-tuning)
CREATE TABLE IF NOT EXISTS public.opportunity_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    opportunity_id uuid NOT NULL,
    decision text NOT NULL CHECK (decision IN ('APPROVE', 'REJECT', 'EDIT', 'ARCHIVE', 'NOTE')),
    reason_code text NULL,
    notes text NULL,
    previous_status text NULL,
    new_status text NOT NULL,
    actor_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES public.opportunities(workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_opportunity_feedback_opp
    ON public.opportunity_feedback (workspace_id, opportunity_id, created_at DESC);

CREATE TRIGGER trg_opportunity_feedback_immutable
    BEFORE UPDATE ON public.opportunity_feedback
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- 4. Episode Briefs (EDIT-001..006 + freeze apos aprovacao)
CREATE TABLE IF NOT EXISTS public.episode_briefs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    brief_group_id uuid NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_brief_id uuid NULL,
    opportunity_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    profile_version_id uuid NOT NULL,
    title text NOT NULL CHECK (char_length(trim(title)) BETWEEN 2 AND 200),
    hook text NOT NULL CHECK (char_length(trim(hook)) >= 2),
    angle text NOT NULL CHECK (char_length(trim(angle)) >= 2),
    outline_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    cta text NOT NULL DEFAULT '',
    target_format text NOT NULL DEFAULT 'long' CHECK (target_format IN ('long', 'short', 'live')),
    source_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    generation_refs_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'DRAFT' CHECK (
        status IN ('DRAFT', 'IN_REVIEW', 'APPROVED', 'ARCHIVED', 'SUPERSEDED')
    ),
    frozen_at timestamptz NULL,
    approved_by uuid NULL,
    approved_at timestamptz NULL,
    content_sha256 text NOT NULL,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, brief_group_id, version),
    UNIQUE (workspace_id, id),
    FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES public.opportunities(workspace_id, id) ON DELETE CASCADE,
    FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_episode_briefs_group
    ON public.episode_briefs (workspace_id, brief_group_id, version DESC);

CREATE OR REPLACE FUNCTION app.guard_frozen_episode_brief()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF OLD.status = 'APPROVED' THEN
        IF NEW.title IS DISTINCT FROM OLD.title
           OR NEW.hook IS DISTINCT FROM OLD.hook
           OR NEW.angle IS DISTINCT FROM OLD.angle
           OR NEW.outline_json IS DISTINCT FROM OLD.outline_json
           OR NEW.cta IS DISTINCT FROM OLD.cta
           OR NEW.target_format IS DISTINCT FROM OLD.target_format
           OR NEW.source_refs_json IS DISTINCT FROM OLD.source_refs_json
           OR NEW.generation_refs_json IS DISTINCT FROM OLD.generation_refs_json
           OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256
           OR NEW.version IS DISTINCT FROM OLD.version THEN
            RAISE EXCEPTION 'Brief aprovado esta congelado e e imutavel; crie uma nova versao (EDIT-003).'
                USING ERRCODE = '22000';
        END IF;
        IF NEW.status NOT IN ('APPROVED', 'SUPERSEDED', 'ARCHIVED') THEN
            RAISE EXCEPTION 'Transicao invalida a partir de APPROVED.'
                USING ERRCODE = '22000';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_episode_briefs_updated_at
    BEFORE UPDATE ON public.episode_briefs
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

CREATE TRIGGER trg_episode_briefs_freeze
    BEFORE UPDATE ON public.episode_briefs
    FOR EACH ROW EXECUTE FUNCTION app.guard_frozen_episode_brief();

-- 5. Brief Decision History (EDIT-006)
CREATE TABLE IF NOT EXISTS public.brief_decision_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    brief_id uuid NOT NULL,
    action text NOT NULL CHECK (action IN ('CREATE', 'UPDATE_DRAFT', 'SUBMIT_REVIEW', 'APPROVE', 'CREATE_VERSION', 'ARCHIVE', 'EXPORT')),
    from_status text NULL,
    to_status text NOT NULL,
    notes text NULL,
    actor_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    FOREIGN KEY (workspace_id, brief_id)
        REFERENCES public.episode_briefs(workspace_id, id) ON DELETE CASCADE
);

CREATE TRIGGER trg_brief_history_immutable
    BEFORE UPDATE ON public.brief_decision_history
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- 6. Editorial Calendar Items (EDIT-005 - zero publicacao automatica)
CREATE TABLE IF NOT EXISTS public.editorial_calendar_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    brief_id uuid NULL,
    title text NOT NULL CHECK (char_length(trim(title)) BETWEEN 2 AND 200),
    scheduled_for date NOT NULL,
    status text NOT NULL DEFAULT 'PLANNED' CHECK (
        status IN ('PLANNED', 'IN_PRODUCTION', 'READY_FOR_MANUAL_PUBLISH', 'PUBLISHED_MANUALLY', 'CANCELED')
    ),
    auto_publish_enabled boolean NOT NULL DEFAULT false CHECK (auto_publish_enabled = false),
    notes text NULL,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_calendar_workspace_date
    ON public.editorial_calendar_items (workspace_id, scheduled_for ASC);

CREATE TRIGGER trg_calendar_items_updated_at
    BEFORE UPDATE ON public.editorial_calendar_items
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- ============================================================================
-- RLS & Permissoes (T-SEC-001 / T-SEC-002)
-- ============================================================================
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'opportunities',
        'evidence_links',
        'opportunity_feedback',
        'episode_briefs',
        'brief_decision_history',
        'editorial_calendar_items'
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
