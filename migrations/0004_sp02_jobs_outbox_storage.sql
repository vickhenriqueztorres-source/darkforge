-- ============================================================================
-- Migration 0004: Fila Unica Postgres, Fencing, Outbox/Inbox, Storage & RLS
-- Subplano: SP-02 (SP-02-T01..T09)
-- ADRs: ADR-003, ADR-004, ADR-012, ADR-013, ADR-015
-- ============================================================================

-- 1. Jobs (catalogo logico unico)
CREATE TABLE IF NOT EXISTS public.jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    channel_id uuid NULL REFERENCES public.channels(id) ON DELETE SET NULL,
    job_type text NOT NULL CHECK (char_length(trim(job_type)) BETWEEN 2 AND 80),
    status text NOT NULL DEFAULT 'QUEUED' CHECK (
        status IN (
            'QUEUED',
            'RUNNING',
            'PAUSED',
            'CANCEL_REQUESTED',
            'CANCELLED',
            'BLOCKED',
            'RECOVERABLE',
            'INTERRUPTED',
            'LOCAL_COMPLETED_PENDING_SYNC',
            'FAILED',
            'SUCCEEDED'
        )
    ),
    priority integer NOT NULL DEFAULT 50 CHECK (priority BETWEEN 1 AND 100),
    idempotency_key text NOT NULL CHECK (char_length(idempotency_key) BETWEEN 8 AND 128),
    payload_hash text NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    checkpoint_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    current_step text NOT NULL DEFAULT 'queued',
    total_steps integer NOT NULL DEFAULT 1 CHECK (total_steps >= 1),
    completed_steps integer NOT NULL DEFAULT 0 CHECK (completed_steps >= 0),
    fencing_token bigint NOT NULL DEFAULT 0,
    worker_id text NULL,
    lease_expires_at timestamptz NULL,
    heartbeat_at timestamptz NULL,
    attempt_count integer NOT NULL DEFAULT 0,
    max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts >= 1),
    next_retry_at timestamptz NULL,
    pause_requested boolean NOT NULL DEFAULT false,
    cancel_requested boolean NOT NULL DEFAULT false,
    error_code text NULL,
    error_message text NULL,
    retryable boolean NOT NULL DEFAULT false,
    correlation_id uuid NOT NULL DEFAULT gen_random_uuid(),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    completed_at timestamptz NULL,
    UNIQUE (workspace_id, job_type, idempotency_key),
    UNIQUE (workspace_id, id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_eligible
    ON public.jobs (priority DESC, next_retry_at ASC NULLS FIRST, created_at ASC)
    WHERE status IN ('QUEUED', 'RECOVERABLE');

CREATE INDEX IF NOT EXISTS idx_jobs_running_lease
    ON public.jobs (lease_expires_at ASC)
    WHERE status = 'RUNNING';

CREATE INDEX IF NOT EXISTS idx_jobs_ws_status_created
    ON public.jobs (workspace_id, status, created_at DESC);

CREATE TRIGGER trg_jobs_updated_at
    BEFORE UPDATE ON public.jobs
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 2. Job Attempts
CREATE TABLE IF NOT EXISTS public.job_attempts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    job_id uuid NOT NULL,
    attempt_number integer NOT NULL,
    fencing_token bigint NOT NULL,
    worker_id text NOT NULL,
    status text NOT NULL DEFAULT 'RUNNING' CHECK (
        status IN ('RUNNING', 'SUCCEEDED', 'FAILED', 'INTERRUPTED', 'PAUSED', 'CANCELLED', 'BLOCKED')
    ),
    error_code text NULL,
    started_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    ended_at timestamptz NULL,
    CONSTRAINT fk_job_attempts_job_ws
        FOREIGN KEY (workspace_id, job_id)
        REFERENCES public.jobs(workspace_id, id)
        ON DELETE CASCADE
);

-- 3. Job Events (stream com sequence_no monotonico para replay SSE last_event_id)
CREATE TABLE IF NOT EXISTS public.job_events (
    sequence_no bigserial PRIMARY KEY,
    workspace_id uuid NOT NULL,
    job_id uuid NOT NULL,
    event_type text NOT NULL,
    step_name text NOT NULL,
    status text NOT NULL,
    message text NOT NULL DEFAULT '',
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_job_events_job_ws
        FOREIGN KEY (workspace_id, job_id)
        REFERENCES public.jobs(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_events_job_seq
    ON public.job_events (workspace_id, job_id, sequence_no ASC);

-- 4. Transactional Outbox & Inbox
CREATE TABLE IF NOT EXISTS public.outbox_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_no bigserial UNIQUE,
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    event_version text NOT NULL DEFAULT 'v1',
    aggregate_type text NOT NULL,
    aggregate_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'DISPATCHED', 'DEAD_LETTER')),
    attempts integer NOT NULL DEFAULT 0,
    dispatched_at timestamptz NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending
    ON public.outbox_events (sequence_no ASC)
    WHERE status = 'PENDING';

CREATE TABLE IF NOT EXISTS public.inbox_events (
    consumer_name text NOT NULL,
    event_id uuid NOT NULL,
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    processed_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    PRIMARY KEY (consumer_name, event_id)
);

-- 5. Idempotent Side Effects Ledger (protecao contra crash pos-efeito externo)
CREATE TABLE IF NOT EXISTS public.idempotent_effects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    effect_scope text NOT NULL,
    effect_key text NOT NULL,
    result_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, effect_scope, effect_key)
);

-- 6. Storage Objects & Artifacts (Storage privado + manifest/checksum)
CREATE TABLE IF NOT EXISTS public.storage_objects (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    bucket text NOT NULL CHECK (bucket IN ('knowledge', 'references', 'exports', 'production')),
    object_path text NOT NULL CHECK (object_path ~ '^[0-9a-f-]{36}/[A-Za-z0-9._/-]+$'),
    sha256 text NULL CHECK (sha256 IS NULL OR sha256 ~ '^[a-f0-9]{64}$'),
    size_bytes bigint NULL CHECK (size_bytes IS NULL OR size_bytes >= 0),
    content_type text NOT NULL DEFAULT 'application/octet-stream',
    status text NOT NULL DEFAULT 'UPLOADING' CHECK (
        status IN ('UPLOADING', 'VERIFYING', 'READY', 'FAILED', 'ORPHANED')
    ),
    retention_until timestamptz NULL,
    created_by_job uuid NULL,
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (bucket, object_path),
    UNIQUE (workspace_id, id)
);

CREATE TRIGGER trg_storage_objects_updated_at
    BEFORE UPDATE ON public.storage_objects
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

CREATE TABLE IF NOT EXISTS public.artifacts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    job_id uuid NOT NULL,
    storage_object_id uuid NULL,
    artifact_type text NOT NULL,
    sha256 text NULL CHECK (sha256 IS NULL OR sha256 ~ '^[a-f0-9]{64}$'),
    manifest_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'READY', 'FAILED')),
    validated boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_artifacts_job_ws
        FOREIGN KEY (workspace_id, job_id)
        REFERENCES public.jobs(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_artifacts_storage_ws
        FOREIGN KEY (workspace_id, storage_object_id)
        REFERENCES public.storage_objects(workspace_id, id)
        ON DELETE RESTRICT
);

CREATE TRIGGER trg_artifacts_updated_at
    BEFORE UPDATE ON public.artifacts
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 7. Buckets privados no Supabase Storage + RLS
INSERT INTO storage.buckets (id, name, public)
VALUES
    ('knowledge', 'knowledge', false),
    ('references', 'references', false),
    ('exports', 'exports', false),
    ('production', 'production', false)
ON CONFLICT (id) DO UPDATE SET public = false;

CREATE POLICY storage_ws_select ON storage.objects
    FOR SELECT TO authenticated
    USING (
        bucket_id IN ('knowledge', 'references', 'exports', 'production')
        AND (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
        AND app.is_workspace_member(((storage.foldername(name))[1])::uuid)
    );

CREATE POLICY storage_ws_insert ON storage.objects
    FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id IN ('knowledge', 'references', 'exports', 'production')
        AND (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
        AND app.has_workspace_role(((storage.foldername(name))[1])::uuid, ARRAY['owner', 'editor'])
    );

CREATE POLICY storage_ws_update ON storage.objects
    FOR UPDATE TO authenticated
    USING (
        bucket_id IN ('knowledge', 'references', 'exports', 'production')
        AND (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
        AND app.has_workspace_role(((storage.foldername(name))[1])::uuid, ARRAY['owner', 'editor'])
    );

CREATE POLICY storage_ws_delete ON storage.objects
    FOR DELETE TO authenticated
    USING (
        bucket_id IN ('knowledge', 'references', 'exports', 'production')
        AND (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
        AND app.has_workspace_role(((storage.foldername(name))[1])::uuid, ARRAY['owner'])
    );

-- 8. RLS + Grants nas tabelas SP-02
REVOKE ALL ON public.jobs FROM PUBLIC, anon;
REVOKE ALL ON public.job_attempts FROM PUBLIC, anon;
REVOKE ALL ON public.job_events FROM PUBLIC, anon;
REVOKE ALL ON public.outbox_events FROM PUBLIC, anon;
REVOKE ALL ON public.inbox_events FROM PUBLIC, anon;
REVOKE ALL ON public.idempotent_effects FROM PUBLIC, anon;
REVOKE ALL ON public.storage_objects FROM PUBLIC, anon;
REVOKE ALL ON public.artifacts FROM PUBLIC, anon;

GRANT SELECT, INSERT, UPDATE ON public.jobs TO authenticated;
GRANT SELECT ON public.job_attempts TO authenticated;
GRANT SELECT ON public.job_events TO authenticated;
GRANT SELECT ON public.outbox_events TO authenticated;
GRANT SELECT ON public.idempotent_effects TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.storage_objects TO authenticated;
GRANT SELECT ON public.artifacts TO authenticated;

ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE public.job_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_attempts FORCE ROW LEVEL SECURITY;
ALTER TABLE public.job_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.outbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.outbox_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.inbox_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.inbox_events FORCE ROW LEVEL SECURITY;
ALTER TABLE public.idempotent_effects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.idempotent_effects FORCE ROW LEVEL SECURITY;
ALTER TABLE public.storage_objects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.storage_objects FORCE ROW LEVEL SECURITY;
ALTER TABLE public.artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.artifacts FORCE ROW LEVEL SECURITY;

CREATE POLICY jobs_select_member ON public.jobs
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY jobs_insert_editor ON public.jobs
    FOR INSERT TO authenticated WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']) AND created_by = auth.uid());
CREATE POLICY jobs_update_editor ON public.jobs
    FOR UPDATE TO authenticated USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY job_attempts_select_member ON public.job_attempts
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY job_events_select_member ON public.job_events
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY outbox_events_select_member ON public.outbox_events
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY inbox_events_select_member ON public.inbox_events
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY idempotent_effects_select_member ON public.idempotent_effects
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));

CREATE POLICY storage_objects_select_member ON public.storage_objects
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));
CREATE POLICY storage_objects_insert_editor ON public.storage_objects
    FOR INSERT TO authenticated WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']) AND created_by = auth.uid());
CREATE POLICY storage_objects_update_editor ON public.storage_objects
    FOR UPDATE TO authenticated USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));
CREATE POLICY storage_objects_delete_owner ON public.storage_objects
    FOR DELETE TO authenticated USING (app.has_workspace_role(workspace_id, ARRAY['owner']));

CREATE POLICY artifacts_select_member ON public.artifacts
    FOR SELECT TO authenticated USING (app.is_workspace_member(workspace_id));

-- 9. Funcoes de Fila Postgres com FOR UPDATE SKIP LOCKED + Fencing Token
CREATE OR REPLACE FUNCTION app.claim_next_job(
    p_worker_id text,
    p_lease_seconds integer DEFAULT 30,
    p_job_types text[] DEFAULT NULL
)
RETURNS TABLE (
    job_id uuid,
    workspace_id uuid,
    channel_id uuid,
    job_type text,
    payload_json jsonb,
    checkpoint_json jsonb,
    fencing_token bigint,
    attempt_count integer,
    correlation_id uuid
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_job public.jobs%ROWTYPE;
    v_now timestamptz := timezone('utc', now());
    v_lease timestamptz := v_now + make_interval(secs => GREATEST(p_lease_seconds, 5));
BEGIN
    SELECT j.* INTO v_job
    FROM public.jobs AS j
    WHERE j.status IN ('QUEUED', 'RECOVERABLE')
      AND (j.next_retry_at IS NULL OR j.next_retry_at <= v_now)
      AND (p_job_types IS NULL OR j.job_type = ANY(p_job_types))
    ORDER BY j.priority DESC, j.created_at ASC
    FOR UPDATE SKIP LOCKED
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    UPDATE public.jobs AS j
    SET status = 'RUNNING',
        worker_id = p_worker_id,
        fencing_token = j.fencing_token + 1,
        attempt_count = j.attempt_count + 1,
        lease_expires_at = v_lease,
        heartbeat_at = v_now,
        pause_requested = false
    WHERE j.id = v_job.id
    RETURNING j.* INTO v_job;

    INSERT INTO public.job_attempts (workspace_id, job_id, attempt_number, fencing_token, worker_id, status)
    VALUES (v_job.workspace_id, v_job.id, v_job.attempt_count, v_job.fencing_token, p_worker_id, 'RUNNING');

    INSERT INTO public.job_events (workspace_id, job_id, event_type, step_name, status, message, payload_json)
    VALUES (
        v_job.workspace_id, v_job.id, 'job.state_changed', 'claimed', 'RUNNING',
        format('Claimed by worker %s (fencing=%s)', p_worker_id, v_job.fencing_token),
        jsonb_build_object('fencing_token', v_job.fencing_token, 'attempt', v_job.attempt_count)
    );

    INSERT INTO public.outbox_events (workspace_id, event_type, aggregate_type, aggregate_id, correlation_id, payload_json)
    VALUES (
        v_job.workspace_id, 'job.state_changed', 'job', v_job.id, v_job.correlation_id,
        jsonb_build_object('status', 'RUNNING', 'fencing_token', v_job.fencing_token)
    );

    RETURN QUERY SELECT
        v_job.id, v_job.workspace_id, v_job.channel_id, v_job.job_type,
        v_job.payload_json, v_job.checkpoint_json, v_job.fencing_token,
        v_job.attempt_count, v_job.correlation_id;
END;
$$;

CREATE OR REPLACE FUNCTION app.heartbeat_job(
    p_job_id uuid,
    p_worker_id text,
    p_fencing_token bigint,
    p_lease_seconds integer DEFAULT 30
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_now timestamptz := timezone('utc', now());
    v_updated integer;
BEGIN
    UPDATE public.jobs AS j
    SET heartbeat_at = v_now,
        lease_expires_at = v_now + make_interval(secs => GREATEST(p_lease_seconds, 5))
    WHERE j.id = p_job_id
      AND j.status = 'RUNNING'
      AND j.worker_id = p_worker_id
      AND j.fencing_token = p_fencing_token;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated = 1;
END;
$$;

CREATE OR REPLACE FUNCTION app.checkpoint_job(
    p_job_id uuid,
    p_fencing_token bigint,
    p_current_step text,
    p_completed_steps integer,
    p_checkpoint jsonb,
    p_message text DEFAULT ''
)
RETURNS TABLE (accepted boolean, pause_requested boolean, cancel_requested boolean)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_job public.jobs%ROWTYPE;
BEGIN
    UPDATE public.jobs AS j
    SET current_step = p_current_step,
        completed_steps = p_completed_steps,
        checkpoint_json = p_checkpoint,
        heartbeat_at = timezone('utc', now())
    WHERE j.id = p_job_id
      AND j.status IN ('RUNNING', 'CANCEL_REQUESTED')
      AND j.fencing_token = p_fencing_token
    RETURNING j.* INTO v_job;

    IF NOT FOUND THEN
        RETURN QUERY SELECT false, false, false;
        RETURN;
    END IF;

    INSERT INTO public.job_events (workspace_id, job_id, event_type, step_name, status, message, payload_json)
    VALUES (
        v_job.workspace_id, v_job.id, 'job.progress_updated', p_current_step, v_job.status, p_message,
        jsonb_build_object('completed_steps', p_completed_steps, 'total_steps', v_job.total_steps)
    );

    RETURN QUERY SELECT true, v_job.pause_requested, v_job.cancel_requested;
END;
$$;

CREATE OR REPLACE FUNCTION app.transition_job_with_fencing(
    p_job_id uuid,
    p_fencing_token bigint,
    p_target_status text,
    p_checkpoint jsonb DEFAULT NULL,
    p_error_code text DEFAULT NULL,
    p_error_message text DEFAULT NULL,
    p_retryable boolean DEFAULT false,
    p_next_retry_at timestamptz DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_job public.jobs%ROWTYPE;
    v_now timestamptz := timezone('utc', now());
    v_event_type text;
BEGIN
    UPDATE public.jobs AS j
    SET status = p_target_status,
        checkpoint_json = COALESCE(p_checkpoint, j.checkpoint_json),
        error_code = p_error_code,
        error_message = p_error_message,
        retryable = p_retryable,
        next_retry_at = p_next_retry_at,
        lease_expires_at = NULL,
        completed_at = CASE WHEN p_target_status IN ('SUCCEEDED', 'CANCELLED', 'FAILED') THEN v_now ELSE j.completed_at END
    WHERE j.id = p_job_id
      AND j.fencing_token = p_fencing_token
      AND j.status IN ('RUNNING', 'CANCEL_REQUESTED', 'LOCAL_COMPLETED_PENDING_SYNC')
    RETURNING j.* INTO v_job;

    IF NOT FOUND THEN
        RETURN false;
    END IF;

    UPDATE public.job_attempts AS ja
    SET status = CASE WHEN p_target_status IN ('QUEUED', 'RECOVERABLE') THEN 'FAILED' ELSE p_target_status END,
        error_code = p_error_code,
        ended_at = v_now
    WHERE ja.job_id = p_job_id
      AND ja.fencing_token = p_fencing_token
      AND ja.ended_at IS NULL;

    v_event_type := CASE
        WHEN p_target_status = 'FAILED' THEN 'job.failed'
        WHEN p_target_status = 'INTERRUPTED' THEN 'job.interrupted'
        ELSE 'job.state_changed'
    END;

    INSERT INTO public.job_events (workspace_id, job_id, event_type, step_name, status, message, payload_json)
    VALUES (
        v_job.workspace_id, v_job.id, v_event_type, v_job.current_step, p_target_status,
        COALESCE(p_error_message, format('Transitioned to %s', p_target_status)),
        jsonb_build_object('error_code', p_error_code, 'retryable', p_retryable)
    );

    INSERT INTO public.outbox_events (workspace_id, event_type, aggregate_type, aggregate_id, correlation_id, payload_json)
    VALUES (
        v_job.workspace_id, v_event_type, 'job', v_job.id, v_job.correlation_id,
        jsonb_build_object('status', p_target_status, 'error_code', p_error_code)
    );

    RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION app.reconcile_expired_leases()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_rec public.jobs%ROWTYPE;
    v_count integer := 0;
    v_now timestamptz := timezone('utc', now());
BEGIN
    FOR v_rec IN
        SELECT * FROM public.jobs
        WHERE status = 'RUNNING'
          AND lease_expires_at IS NOT NULL
          AND lease_expires_at < v_now
        FOR UPDATE SKIP LOCKED
    LOOP
        UPDATE public.jobs
        SET status = 'RECOVERABLE',
            lease_expires_at = NULL,
            next_retry_at = v_now,
            error_code = 'LEASE_EXPIRED',
            error_message = 'Worker heartbeat expirado; job pronto para retomada a partir do ultimo checkpoint.'
        WHERE id = v_rec.id;

        UPDATE public.job_attempts
        SET status = 'INTERRUPTED',
            error_code = 'LEASE_EXPIRED',
            ended_at = v_now
        WHERE job_id = v_rec.id
          AND fencing_token = v_rec.fencing_token
          AND ended_at IS NULL;

        INSERT INTO public.job_events (workspace_id, job_id, event_type, step_name, status, message, payload_json)
        VALUES (
            v_rec.workspace_id, v_rec.id, 'job.interrupted', v_rec.current_step, 'RECOVERABLE',
            'Lease expirado; reconciliado para RECOVERABLE',
            jsonb_build_object('expired_fencing_token', v_rec.fencing_token)
        );

        INSERT INTO public.outbox_events (workspace_id, event_type, aggregate_type, aggregate_id, correlation_id, payload_json)
        VALUES (
            v_rec.workspace_id, 'job.interrupted', 'job', v_rec.id, v_rec.correlation_id,
            jsonb_build_object('status', 'RECOVERABLE', 'expired_fencing_token', v_rec.fencing_token)
        );

        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$;

REVOKE ALL ON FUNCTION app.claim_next_job(text, integer, text[]) FROM PUBLIC, authenticated, anon;
REVOKE ALL ON FUNCTION app.heartbeat_job(uuid, text, bigint, integer) FROM PUBLIC, authenticated, anon;
REVOKE ALL ON FUNCTION app.checkpoint_job(uuid, bigint, text, integer, jsonb, text) FROM PUBLIC, authenticated, anon;
REVOKE ALL ON FUNCTION app.transition_job_with_fencing(uuid, bigint, text, jsonb, text, text, boolean, timestamptz) FROM PUBLIC, authenticated, anon;
REVOKE ALL ON FUNCTION app.reconcile_expired_leases() FROM PUBLIC, authenticated, anon;
