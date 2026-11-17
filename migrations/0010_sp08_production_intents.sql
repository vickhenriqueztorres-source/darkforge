-- ============================================================================
-- Migration 0010: Production Intents & DarkForge Single-Writer Gate
-- Subplano: SP-08 (PROD-001..005, T-DF-001)
-- ADRs: ADR-003, ADR-004, ADR-008, ADR-012, ADR-016
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.production_intents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    brief_id uuid NOT NULL,
    brief_version integer NOT NULL CHECK (brief_version >= 1),
    brief_content_sha256 text NOT NULL,
    pipeline_version text NOT NULL DEFAULT 'media_vertical_v1',
    idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 8 AND 128),
    job_id uuid NULL,
    external_darkforge_job_id text NULL,
    status text NOT NULL DEFAULT 'INTENT_CREATED' CHECK (
        status IN ('INTENT_CREATED', 'DISPATCHED', 'RUNNING', 'PAUSED', 'CANCELLED', 'BLOCKED', 'READY', 'FAILED')
    ),
    manifest_validated boolean NOT NULL DEFAULT false,
    manifest_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    error_code text NULL,
    error_message text NULL,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, idempotency_key),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_prod_intent_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_prod_intent_brief_ws
        FOREIGN KEY (workspace_id, brief_id)
        REFERENCES public.episode_briefs(workspace_id, id) ON DELETE CASCADE,
    CONSTRAINT fk_prod_intent_job_ws
        FOREIGN KEY (workspace_id, job_id)
        REFERENCES public.jobs(workspace_id, id) ON DELETE SET NULL,
    CONSTRAINT chk_ready_requires_validated_manifest
        CHECK (status <> 'READY' OR manifest_validated = true)
);

CREATE INDEX IF NOT EXISTS idx_production_intents_ws_brief
    ON public.production_intents (workspace_id, brief_id, created_at DESC);

CREATE TRIGGER trg_production_intents_updated_at
    BEFORE UPDATE ON public.production_intents
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

ALTER TABLE public.production_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.production_intents FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.production_intents FROM PUBLIC, anon;
GRANT SELECT, INSERT, UPDATE ON public.production_intents TO authenticated;

CREATE POLICY p_production_intents_select ON public.production_intents
    FOR SELECT TO authenticated
    USING (app.is_workspace_member(workspace_id));

CREATE POLICY p_production_intents_insert ON public.production_intents
    FOR INSERT TO authenticated
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY p_production_intents_update ON public.production_intents
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));
