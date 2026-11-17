-- ============================================================================
-- Migration 0015: DarkForge Studio UI — Salas, Equipe de Agentes, Runs,
--                 Eventos, Outputs, Proveniencia, Handoffs, Aprovacoes e Views
-- Subplanos: UI-01 (UI-01-T01..T06)
-- Referencia: docs/studio-ui/database.md, docs/studio-ui/adr/ADR-UI-001-encaixe.md
-- ============================================================================

-- 1. Catalogos globais
CREATE TABLE IF NOT EXISTS public.studio_rooms (
    key        text PRIMARY KEY,
    label      text NOT NULL,
    sort_order integer NOT NULL DEFAULT 0
);

INSERT INTO public.studio_rooms (key, label, sort_order) VALUES
    ('sala_dados',            'Sala de Dados',            10),
    ('pesquisa',              'Pesquisa',                 20),
    ('mesa_agentes',          'Agentes de IA',            30),
    ('gravacao',              'Gravação',                 40),
    ('design_thumbnail',      'Design – Thumbnail',       50),
    ('estrategia_publicacao', 'Estratégia e Publicação',  60)
ON CONFLICT (key) DO UPDATE
SET label = EXCLUDED.label,
    sort_order = EXCLUDED.sort_order;

CREATE TABLE IF NOT EXISTS public.agent_definitions (
    key               text PRIMARY KEY,
    display_name      text NOT NULL,
    room_key          text NOT NULL REFERENCES public.studio_rooms(key),
    description       text NOT NULL,
    output_types      text[] NOT NULL,
    requires_approval boolean NOT NULL DEFAULT false,
    contract_version  integer NOT NULL DEFAULT 1,
    active            boolean NOT NULL DEFAULT true
);

INSERT INTO public.agent_definitions (key, display_name, room_key, description, output_types, requires_approval, contract_version, active) VALUES
    ('dados',      'Analista de Dados',    'sala_dados',            'Interpreta analytics sincronizados do canal',  ARRAY['channel_insight'],    false, 1, true),
    ('pesquisa',   'Pesquisador',          'pesquisa',              'Referências públicas e validação de tema',     ARRAY['research_findings'],  false, 1, true),
    ('estrategia', 'Estrategista',         'mesa_agentes',          'Gera e pontua oportunidades com evidência',    ARRAY['opportunity'],        true,  1, true),
    ('titulos',    'Especialista Títulos', 'mesa_agentes',          'Análise e alternativas originais de título',   ARRAY['title_options'],      false, 1, true),
    ('roteiro',    'Roteirista',           'mesa_agentes',          'Outline e rascunho de roteiro na voz do canal',ARRAY['script_draft'],       false, 1, true),
    ('thumbnail',  'Designer de Capa',     'design_thumbnail',      'Conceitos originais de thumbnail',             ARRAY['thumbnail_concepts'], false, 1, true),
    ('edicao',     'Produção',             'gravacao',              'Acompanha produção DarkForge e quality checks',ARRAY['production_status'],  false, 1, true),
    ('publicacao', 'Publicação',           'estrategia_publicacao', 'Plano de publicação para aprovação humana',    ARRAY['publication_plan'],   true,  1, true)
ON CONFLICT (key) DO UPDATE
SET display_name = EXCLUDED.display_name,
    room_key = EXCLUDED.room_key,
    description = EXCLUDED.description,
    output_types = EXCLUDED.output_types,
    requires_approval = EXCLUDED.requires_approval,
    contract_version = EXCLUDED.contract_version,
    active = EXCLUDED.active;

-- 2. Equipe de agentes por canal
CREATE TABLE IF NOT EXISTS public.channel_agents (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id         uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id           uuid NOT NULL,
    agent_key            text NOT NULL REFERENCES public.agent_definitions(key),
    enabled              boolean NOT NULL DEFAULT true,
    display_name         text NULL,
    avatar_key           text NULL,
    config               jsonb NOT NULL DEFAULT '{}'::jsonb,
    model_policy         jsonb NOT NULL DEFAULT '{"mode":"local_only","external_consent":false}'::jsonb,
    monthly_budget_cents integer NULL CHECK (monthly_budget_cents IS NULL OR monthly_budget_cents >= 0),
    created_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at           timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (channel_id, agent_key),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_channel_agents_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_channel_agents_workspace
    ON public.channel_agents (workspace_id, channel_id);

CREATE TRIGGER trg_channel_agents_updated_at
    BEFORE UPDATE ON public.channel_agents
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- Trigger idempotente para criar os 8 agentes ao criar um canal
CREATE OR REPLACE FUNCTION app.seed_channel_agents_for_channel()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
    INSERT INTO public.channel_agents (workspace_id, channel_id, agent_key, enabled, avatar_key, config)
    SELECT
        NEW.workspace_id,
        NEW.id,
        ad.key,
        CASE WHEN ad.key = 'edicao' THEN false ELSE true END,
        ad.key,
        CASE
            WHEN ad.key = 'edicao' THEN jsonb_build_object('unavailable_reason', 'DARKFORGE_UNAVAILABLE')
            ELSE '{}'::jsonb
        END
    FROM public.agent_definitions AS ad
    WHERE ad.active = true
    ON CONFLICT (channel_id, agent_key) DO NOTHING;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_channels_seed_agents ON public.channels;
CREATE TRIGGER trg_channels_seed_agents
    AFTER INSERT ON public.channels
    FOR EACH ROW EXECUTE FUNCTION app.seed_channel_agents_for_channel();

-- Backfill idempotente para canais existentes
INSERT INTO public.channel_agents (workspace_id, channel_id, agent_key, enabled, avatar_key, config)
SELECT
    c.workspace_id,
    c.id,
    ad.key,
    CASE WHEN ad.key = 'edicao' THEN false ELSE true END,
    ad.key,
    CASE
        WHEN ad.key = 'edicao' THEN jsonb_build_object('unavailable_reason', 'DARKFORGE_UNAVAILABLE')
        ELSE '{}'::jsonb
    END
FROM public.channels AS c
CROSS JOIN public.agent_definitions AS ad
WHERE ad.active = true
ON CONFLICT (channel_id, agent_key) DO NOTHING;

-- 3. Content items (episodio percorrendo o estúdio)
CREATE TABLE IF NOT EXISTS public.content_items (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id          uuid NOT NULL,
    working_title       text NOT NULL CHECK (char_length(trim(working_title)) BETWEEN 2 AND 240),
    opportunity_id      uuid NULL,
    brief_id            uuid NULL,
    brief_version       integer NULL CHECK (brief_version IS NULL OR brief_version >= 1),
    stage               text NOT NULL DEFAULT 'ideia' CHECK (
        stage IN ('ideia','pesquisa','estrategia','roteiro','design','producao','publicacao','publicado_manual','arquivado')
    ),
    status              text NOT NULL DEFAULT 'ativo' CHECK (
        status IN ('ativo','aguardando_aprovacao','bloqueado','concluido','arquivado')
    ),
    scheduled_for       timestamptz NULL,
    published_video_url text NULL,
    published_at        timestamptz NULL,
    created_by          uuid NOT NULL,
    created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_content_items_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_content_items_opportunity_ws
        FOREIGN KEY (workspace_id, opportunity_id)
        REFERENCES public.opportunities(workspace_id, id)
        ON DELETE SET NULL,
    CONSTRAINT fk_content_items_brief_ws
        FOREIGN KEY (workspace_id, brief_id)
        REFERENCES public.episode_briefs(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_content_items_channel_stage
    ON public.content_items (channel_id, stage, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_items_workspace
    ON public.content_items (workspace_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_content_items_opportunity
    ON public.content_items (opportunity_id) WHERE opportunity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_content_items_brief
    ON public.content_items (brief_id) WHERE brief_id IS NOT NULL;

CREATE TRIGGER trg_content_items_updated_at
    BEFORE UPDATE ON public.content_items
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 4. Agent runs (ligado a fila unica public.jobs)
CREATE TABLE IF NOT EXISTS public.agent_runs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id          uuid NOT NULL,
    channel_agent_id    uuid NOT NULL,
    agent_key           text NOT NULL REFERENCES public.agent_definitions(key),
    content_item_id     uuid NULL,
    job_id              uuid NULL,
    parent_run_id       uuid NULL REFERENCES public.agent_runs(id) ON DELETE SET NULL,
    status              text NOT NULL DEFAULT 'queued' CHECK (
        status IN ('queued','working','waiting_input','needs_review','waiting_approval','blocked','failed','cancelled','done')
    ),
    stage_label         text NULL,
    progress            numeric(5,4) NULL CHECK (progress IS NULL OR (progress >= 0 AND progress <= 1)),
    attempt             integer NOT NULL DEFAULT 1 CHECK (attempt >= 1),
    idempotency_key     text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 4 AND 160),
    input_hash          text NULL,
    prompt_version      text NULL,
    model_id            text NULL,
    provider            text NULL,
    cost_estimate_cents integer NULL CHECK (cost_estimate_cents IS NULL OR cost_estimate_cents >= 0),
    heartbeat_at        timestamptz NULL,
    started_at          timestamptz NULL,
    finished_at         timestamptz NULL,
    error_code          text NULL,
    error_message       text NULL,
    created_at          timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, idempotency_key),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_agent_runs_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_runs_agent_ws
        FOREIGN KEY (workspace_id, channel_agent_id)
        REFERENCES public.channel_agents(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_runs_item_ws
        FOREIGN KEY (workspace_id, content_item_id)
        REFERENCES public.content_items(workspace_id, id)
        ON DELETE SET NULL,
    CONSTRAINT fk_agent_runs_job_ws
        FOREIGN KEY (workspace_id, job_id)
        REFERENCES public.jobs(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_channel_status
    ON public.agent_runs (channel_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_item_agent
    ON public.agent_runs (content_item_id, agent_key, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_job
    ON public.agent_runs (job_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_channel_agent
    ON public.agent_runs (channel_agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_runs_parent
    ON public.agent_runs (parent_run_id) WHERE parent_run_id IS NOT NULL;

-- 5. Agent events (feed "Atividade dos Agentes" + replay por cursor)
CREATE TABLE IF NOT EXISTS public.agent_events (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id    uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id      uuid NOT NULL,
    run_id          uuid NOT NULL,
    content_item_id uuid NULL,
    agent_key       text NOT NULL REFERENCES public.agent_definitions(key),
    seq             integer NOT NULL CHECK (seq >= 1),
    event_type      text NOT NULL CHECK (
        event_type IN (
            'run_queued','run_started','stage_changed','progress',
            'output_saved','output_validated','needs_review','handoff_created',
            'blocked','failed','cancelled','completed'
        )
    ),
    summary         text NOT NULL,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (run_id, seq),
    CONSTRAINT fk_agent_events_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_events_run_ws
        FOREIGN KEY (workspace_id, run_id)
        REFERENCES public.agent_runs(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_events_item_ws
        FOREIGN KEY (workspace_id, content_item_id)
        REFERENCES public.content_items(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_events_channel_cursor
    ON public.agent_events (channel_id, id);
CREATE INDEX IF NOT EXISTS idx_agent_events_item
    ON public.agent_events (content_item_id, id);
CREATE INDEX IF NOT EXISTS idx_agent_events_workspace
    ON public.agent_events (workspace_id, channel_id, id);

CREATE TRIGGER trg_agent_events_immutable
    BEFORE UPDATE OR DELETE ON public.agent_events
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- 6. Agent outputs & proveniencia
CREATE TABLE IF NOT EXISTS public.agent_outputs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id        uuid NOT NULL,
    run_id            uuid NULL,
    content_item_id   uuid NULL,
    agent_key         text NOT NULL REFERENCES public.agent_definitions(key),
    output_type       text NOT NULL,
    schema_version    integer NOT NULL DEFAULT 1,
    version           integer NOT NULL CHECK (version >= 1),
    content           jsonb NOT NULL,
    content_hash      text NOT NULL,
    status            text NOT NULL DEFAULT 'draft' CHECK (
        status IN ('draft','validated','needs_review','approved','rejected','superseded')
    ),
    validation        jsonb NOT NULL DEFAULT '{}'::jsonb,
    originality_score numeric(5,4) NULL,
    author_kind       text NOT NULL DEFAULT 'agent' CHECK (author_kind IN ('agent', 'human')),
    author_user_id    uuid NULL,
    parent_output_id  uuid NULL REFERENCES public.agent_outputs(id) ON DELETE SET NULL,
    created_at        timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id),
    CONSTRAINT chk_agent_outputs_author
        CHECK (author_kind = 'human' OR run_id IS NOT NULL),
    CONSTRAINT fk_agent_outputs_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_outputs_run_ws
        FOREIGN KEY (workspace_id, run_id)
        REFERENCES public.agent_runs(workspace_id, id)
        ON DELETE SET NULL,
    CONSTRAINT fk_agent_outputs_item_ws
        FOREIGN KEY (workspace_id, content_item_id)
        REFERENCES public.content_items(workspace_id, id)
        ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_outputs_item_type_version
    ON public.agent_outputs (content_item_id, output_type, version)
    WHERE content_item_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_outputs_channel_type_version
    ON public.agent_outputs (channel_id, output_type, version)
    WHERE content_item_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_outputs_run_type_hash
    ON public.agent_outputs (run_id, output_type, content_hash)
    WHERE run_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_agent_outputs_channel
    ON public.agent_outputs (channel_id, output_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_outputs_workspace
    ON public.agent_outputs (workspace_id, channel_id);

CREATE TABLE IF NOT EXISTS public.agent_output_sources (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    output_id    uuid NOT NULL,
    source_kind  text NOT NULL CHECK (
        source_kind IN ('metric','research_reference','knowledge_chunk','profile_version','agent_output','artifact')
    ),
    source_id    text NOT NULL,
    locator      text NULL,
    note         text NULL,
    CONSTRAINT fk_agent_output_sources_output_ws
        FOREIGN KEY (workspace_id, output_id)
        REFERENCES public.agent_outputs(workspace_id, id)
        ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_output_sources
    ON public.agent_output_sources (output_id, source_kind, source_id, COALESCE(locator, ''));
CREATE INDEX IF NOT EXISTS idx_agent_output_sources_ws
    ON public.agent_output_sources (workspace_id, output_id);

-- 7. Handoffs entre agentes
CREATE TABLE IF NOT EXISTS public.agent_handoffs (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id       uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id         uuid NOT NULL,
    content_item_id    uuid NOT NULL,
    from_run_id        uuid NOT NULL,
    output_id          uuid NOT NULL,
    to_agent_key       text NOT NULL REFERENCES public.agent_definitions(key),
    status             text NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending','accepted','consumed','cancelled')
    ),
    consumed_by_run_id uuid NULL,
    created_at         timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (output_id, to_agent_key),
    CONSTRAINT fk_agent_handoffs_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_handoffs_item_ws
        FOREIGN KEY (workspace_id, content_item_id)
        REFERENCES public.content_items(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_handoffs_from_run_ws
        FOREIGN KEY (workspace_id, from_run_id)
        REFERENCES public.agent_runs(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_handoffs_output_ws
        FOREIGN KEY (workspace_id, output_id)
        REFERENCES public.agent_outputs(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_agent_handoffs_consumed_ws
        FOREIGN KEY (workspace_id, consumed_by_run_id)
        REFERENCES public.agent_runs(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_handoffs_pending
    ON public.agent_handoffs (channel_id, to_agent_key, status);
CREATE INDEX IF NOT EXISTS idx_agent_handoffs_item
    ON public.agent_handoffs (content_item_id, to_agent_key, status);

-- 8. Aprovacoes humanas versionadas
CREATE TABLE IF NOT EXISTS public.approvals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id      uuid NOT NULL,
    content_item_id uuid NULL,
    target_kind     text NOT NULL CHECK (target_kind IN ('agent_output','opportunity','brief','publication_plan')),
    target_id       uuid NOT NULL,
    target_version  integer NOT NULL CHECK (target_version >= 1),
    decision        text NOT NULL CHECK (decision IN ('approved','rejected','changes_requested')),
    reason          text NULL,
    decided_by      uuid NOT NULL,
    decided_at      timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_approvals_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_approvals_item_ws
        FOREIGN KEY (workspace_id, content_item_id)
        REFERENCES public.content_items(workspace_id, id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_approvals_target
    ON public.approvals (target_kind, target_id, target_version DESC);
CREATE INDEX IF NOT EXISTS idx_approvals_channel
    ON public.approvals (workspace_id, channel_id, decided_at DESC);

CREATE TRIGGER trg_approvals_immutable
    BEFORE UPDATE OR DELETE ON public.approvals
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- 9. RLS & Grants (navegador so le runs/events/outputs/handoffs)
REVOKE ALL ON public.studio_rooms FROM PUBLIC, anon;
REVOKE ALL ON public.agent_definitions FROM PUBLIC, anon;
REVOKE ALL ON public.channel_agents FROM PUBLIC, anon;
REVOKE ALL ON public.content_items FROM PUBLIC, anon;
REVOKE ALL ON public.agent_runs FROM PUBLIC, anon;
REVOKE ALL ON public.agent_events FROM PUBLIC, anon;
REVOKE ALL ON public.agent_outputs FROM PUBLIC, anon;
REVOKE ALL ON public.agent_output_sources FROM PUBLIC, anon;
REVOKE ALL ON public.agent_handoffs FROM PUBLIC, anon;
REVOKE ALL ON public.approvals FROM PUBLIC, anon;

GRANT SELECT ON public.studio_rooms TO authenticated;
GRANT SELECT ON public.agent_definitions TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.channel_agents TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.content_items TO authenticated;
GRANT SELECT ON public.agent_runs TO authenticated;
GRANT SELECT ON public.agent_events TO authenticated;
GRANT SELECT ON public.agent_outputs TO authenticated;
GRANT SELECT ON public.agent_output_sources TO authenticated;
GRANT SELECT ON public.agent_handoffs TO authenticated;
GRANT SELECT, INSERT ON public.approvals TO authenticated;

ALTER TABLE public.studio_rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.studio_rooms FORCE ROW LEVEL SECURITY;
ALTER TABLE public.agent_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_definitions FORCE ROW LEVEL SECURITY;
ALTER TABLE public.channel_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.channel_agents FORCE ROW LEVEL SECURITY;
ALTER TABLE public.content_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.content_items FORCE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.agent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.agent_outputs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_outputs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.agent_output_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_output_sources FORCE ROW LEVEL SECURITY;
ALTER TABLE public.agent_handoffs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_handoffs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.approvals FORCE ROW LEVEL SECURITY;

CREATE POLICY studio_rooms_read ON public.studio_rooms
    FOR SELECT TO authenticated USING (true);
CREATE POLICY agent_definitions_read ON public.agent_definitions
    FOR SELECT TO authenticated USING (true);

CREATE POLICY channel_agents_select ON public.channel_agents
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY channel_agents_insert ON public.channel_agents
    FOR INSERT TO authenticated WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));
CREATE POLICY channel_agents_update ON public.channel_agents
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY content_items_select ON public.content_items
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY content_items_insert ON public.content_items
    FOR INSERT TO authenticated
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']) AND created_by = auth.uid());
CREATE POLICY content_items_update ON public.content_items
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY agent_runs_read ON public.agent_runs
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY agent_events_read ON public.agent_events
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY agent_outputs_read ON public.agent_outputs
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY agent_output_sources_read ON public.agent_output_sources
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY agent_handoffs_read ON public.agent_handoffs
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));

CREATE POLICY approvals_read ON public.approvals
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY approvals_insert ON public.approvals
    FOR INSERT TO authenticated
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']) AND decided_by = auth.uid());

-- 10. Views de leitura para a UI (respeitam RLS com security_invoker = true)
CREATE OR REPLACE VIEW public.v_studio_agent_state
WITH (security_invoker = true) AS
SELECT DISTINCT ON (ca.id)
    ca.workspace_id,
    ca.channel_id,
    ca.id AS channel_agent_id,
    ca.agent_key,
    ca.enabled,
    ca.config,
    ca.model_policy,
    ca.monthly_budget_cents,
    ad.room_key,
    ad.description,
    ad.requires_approval,
    ad.contract_version,
    COALESCE(NULLIF(trim(ca.display_name), ''), ad.display_name) AS display_name,
    COALESCE(NULLIF(trim(ca.avatar_key), ''), ca.agent_key) AS avatar_key,
    r.id AS run_id,
    r.job_id,
    r.content_item_id,
    CASE
        WHEN NOT ca.enabled THEN 'disabled'
        WHEN r.id IS NULL THEN 'idle'
        WHEN r.status = 'working' AND (r.heartbeat_at IS NULL OR r.heartbeat_at < timezone('utc', now()) - interval '2 minutes') THEN 'no_signal'
        ELSE r.status
    END AS status,
    r.stage_label,
    r.progress,
    r.attempt,
    r.heartbeat_at,
    r.started_at,
    r.finished_at,
    r.error_code,
    r.error_message,
    r.cost_estimate_cents,
    r.created_at AS run_created_at
FROM public.channel_agents AS ca
JOIN public.agent_definitions AS ad ON ad.key = ca.agent_key
LEFT JOIN public.agent_runs AS r ON r.channel_agent_id = ca.id
ORDER BY ca.id, r.created_at DESC NULLS LAST;

CREATE OR REPLACE VIEW public.v_studio_room_state
WITH (security_invoker = true) AS
SELECT
    s.workspace_id,
    s.channel_id,
    sr.key AS room_key,
    sr.label AS room_label,
    sr.sort_order,
    COUNT(*) FILTER (WHERE s.enabled AND s.status = 'working') AS working,
    COUNT(*) FILTER (WHERE s.enabled AND s.status IN ('needs_review', 'waiting_approval')) AS awaiting_human,
    COUNT(*) FILTER (WHERE s.enabled AND s.status IN ('blocked', 'no_signal')) AS blocked,
    COUNT(*) FILTER (WHERE s.enabled AND s.status = 'failed') AS failed,
    COUNT(*) FILTER (WHERE s.enabled) AS agents,
    COUNT(*) FILTER (WHERE NOT s.enabled) AS disabled_agents
FROM public.studio_rooms AS sr
JOIN public.v_studio_agent_state AS s ON s.room_key = sr.key
GROUP BY s.workspace_id, s.channel_id, sr.key, sr.label, sr.sort_order;

CREATE OR REPLACE VIEW public.v_content_pipeline
WITH (security_invoker = true) AS
SELECT
    ci.id AS content_item_id,
    ci.workspace_id,
    ci.channel_id,
    ci.working_title,
    ci.opportunity_id,
    ci.brief_id,
    ci.brief_version,
    ci.stage,
    ci.status,
    ci.scheduled_for,
    ci.published_video_url,
    ci.published_at,
    ci.created_at,
    ci.updated_at,
    COALESCE(
        (
            SELECT jsonb_object_agg(
                sub.output_type,
                jsonb_build_object(
                    'output_id', sub.id,
                    'version', sub.version,
                    'status', sub.status,
                    'agent_key', sub.agent_key,
                    'created_at', sub.created_at
                )
            )
            FROM (
                SELECT DISTINCT ON (ao.output_type)
                    ao.id, ao.output_type, ao.version, ao.status, ao.agent_key, ao.created_at
                FROM public.agent_outputs AS ao
                WHERE ao.content_item_id = ci.id
                ORDER BY ao.output_type, ao.version DESC
            ) AS sub
        ),
        '{}'::jsonb
    ) AS latest_outputs
FROM public.content_items AS ci;

GRANT SELECT ON public.v_studio_agent_state TO authenticated;
GRANT SELECT ON public.v_studio_room_state TO authenticated;
GRANT SELECT ON public.v_content_pipeline TO authenticated;

-- 11. Opcional: registrar agent_events na publicacao Realtime se existir
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.agent_events;
        EXCEPTION
            WHEN duplicate_object THEN NULL;
            WHEN others THEN NULL;
        END;
    END IF;
END;
$$;
