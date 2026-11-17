-- ============================================================================
-- Migration 0013: 4-Phase Reverse Engineering Engine & Experiment Batches (SP-19..SP-23)
-- ============================================================================

-- 1. Fase 1: Auditoria de 6 Criterios para Canais de Referencia (5 a 10 canais)
CREATE TABLE IF NOT EXISTS public.reference_channel_audits (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    external_channel_id text NOT NULL,
    display_name text NOT NULL,
    approved boolean NOT NULL DEFAULT false,
    passed_criteria_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    failed_criteria_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    channel_mean_views double precision NOT NULL DEFAULT 0,
    outlier_hits_count integer NOT NULL DEFAULT 0,
    max_outlier_ratio double precision NOT NULL DEFAULT 0,
    ranking_score double precision NOT NULL DEFAULT 0,
    warnings_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id) ON DELETE CASCADE
);

-- 2. Fase 2: Outliers de 20-30 videos + Velocidade Views/Dia + Filtro Falso Positivo
CREATE TABLE IF NOT EXISTS public.viral_outlier_snapshots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    external_video_id text NOT NULL,
    external_channel_id text NOT NULL,
    channel_name text NOT NULL,
    title text NOT NULL,
    views bigint NOT NULL DEFAULT 0,
    days_since_upload integer NOT NULL DEFAULT 1,
    views_per_day double precision NOT NULL DEFAULT 0,
    channel_mean_views double precision NOT NULL DEFAULT 0,
    outlier_ratio double precision NOT NULL DEFAULT 0,
    pattern_key text NOT NULL DEFAULT 'geral::long',
    confirmed_multi_channel boolean NOT NULL DEFAULT false,
    is_false_positive boolean NOT NULL DEFAULT false,
    false_positive_reasons_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

-- 3. Fase 3: Autopsia Anti-Plagio (Package + 0-15s/15-30s/Meio + Comentarios)
CREATE TABLE IF NOT EXISTS public.video_autopsies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    external_video_id text NOT NULL,
    original_title text NOT NULL,
    package_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    script_retention_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    comment_gaps_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    narrative_archetype text NOT NULL,
    confidence numeric(5,4) NOT NULL DEFAULT 0,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id)
);

-- 4. Fase 4: Mecanismos Transferiveis (Tema + Angulo + Emocao + Estrutura + Formato)
CREATE TABLE IF NOT EXISTS public.transferable_mechanisms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    formula_theme text NOT NULL,
    formula_angle text NOT NULL,
    formula_emotion text NOT NULL,
    formula_structure text NOT NULL,
    formula_format text NOT NULL DEFAULT 'long',
    synthesized_title text NOT NULL,
    synthesized_thumb_concept text NOT NULL,
    synthesized_outline_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    filled_comment_gaps_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    originality_max_similarity double precision NOT NULL DEFAULT 0,
    originality_blocked boolean NOT NULL DEFAULT false,
    source_autopsy_ids_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    sample_warning text NULL,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

-- 5. Fase 4 Execucao: Lote de Teste (Impressoes, CTR, Retencao 30s)
CREATE TABLE IF NOT EXISTS public.experiment_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NOT NULL,
    mechanism_id uuid NULL,
    brief_id uuid NULL,
    title text NOT NULL,
    status text NOT NULL DEFAULT 'PLANNED' CHECK (status IN ('PLANNED', 'PUBLISHED_MEASURING', 'VALIDATED', 'INCONCLUSIVE', 'REJECTED')),
    impressions bigint NULL,
    ctr_pct double precision NULL,
    retention_30s_pct double precision NULL,
    outcome_notes text NOT NULL DEFAULT '',
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TRIGGER trg_experiment_batches_updated_at
    BEFORE UPDATE ON public.experiment_batches
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- ============================================================================
-- RLS & Permissoes
-- ============================================================================
DO $$
DECLARE
    tbl text;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'reference_channel_audits',
        'viral_outlier_snapshots',
        'video_autopsies',
        'transferable_mechanisms',
        'experiment_batches'
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
