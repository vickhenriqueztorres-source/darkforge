-- ============================================================================
-- Migration 0001: Workspaces, Memberships, Channels, Versioned Profiles & Audit
-- Subplano: SP-01 (SP-01-T02, SP-01-T06, SP-01-T07)
-- ADRs: ADR-004, ADR-009, ADR-011
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    NEW.updated_at := timezone('utc', now());
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION app.forbid_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    RAISE EXCEPTION 'Historical records in % are immutable; create a new version instead.', TG_TABLE_NAME
        USING ERRCODE = 'check_violation';
END;
$$;

-- 1. Workspaces
CREATE TABLE IF NOT EXISTS public.workspaces (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL CHECK (char_length(trim(name)) BETWEEN 2 AND 120),
    slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$'),
    settings_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE TRIGGER trg_workspaces_updated_at
    BEFORE UPDATE ON public.workspaces
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 2. Workspace Memberships (autorizacao nunca vem de user_metadata)
CREATE TABLE IF NOT EXISTS public.workspace_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    user_id uuid NOT NULL,
    role text NOT NULL CHECK (role IN ('owner', 'editor', 'viewer')),
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_workspace_members_user_ws
    ON public.workspace_members (user_id, workspace_id);

CREATE TRIGGER trg_workspace_members_updated_at
    BEFORE UPDATE ON public.workspace_members
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 3. Channels (varios canais por workspace)
CREATE TABLE IF NOT EXISTS public.channels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    platform text NOT NULL DEFAULT 'youtube' CHECK (platform IN ('youtube')),
    external_channel_id text NULL,
    display_name text NOT NULL CHECK (char_length(trim(display_name)) BETWEEN 1 AND 120),
    handle text NULL,
    status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    active_profile_version_id uuid NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    updated_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (workspace_id, id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_channels_workspace_platform_ext
    ON public.channels (workspace_id, platform, external_channel_id)
    WHERE external_channel_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_channels_workspace_created
    ON public.channels (workspace_id, created_at DESC);

CREATE TRIGGER trg_channels_updated_at
    BEFORE UPDATE ON public.channels
    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();

-- 4. Channel Profile Versions (imutavel e versionada: CH-001..CH-004, ADR-009)
CREATE TABLE IF NOT EXISTS public.channel_profile_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    version_number integer NOT NULL CHECK (version_number >= 1),
    name text NOT NULL CHECK (char_length(trim(name)) BETWEEN 1 AND 120),
    platform text NOT NULL DEFAULT 'youtube' CHECK (platform IN ('youtube')),
    language text NOT NULL CHECK (char_length(trim(language)) BETWEEN 2 AND 20),
    country text NOT NULL CHECK (char_length(trim(country)) BETWEEN 2 AND 10),
    timezone text NOT NULL CHECK (char_length(trim(timezone)) BETWEEN 2 AND 64),
    niche text NOT NULL CHECK (char_length(trim(niche)) BETWEEN 1 AND 160),
    positioning text NOT NULL DEFAULT '',
    editorial_theme text NOT NULL DEFAULT '',
    audience_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    pillars_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    voice_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    formats_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    objectives_json jsonb NOT NULL DEFAULT '[]'::jsonb,
    restrictions_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    effective_from timestamptz NOT NULL DEFAULT timezone('utc', now()),
    change_summary text NOT NULL DEFAULT 'Versão inicial',
    created_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    UNIQUE (channel_id, version_number),
    UNIQUE (workspace_id, id),
    CONSTRAINT fk_profile_versions_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_profile_versions_channel_ver
    ON public.channel_profile_versions (workspace_id, channel_id, version_number DESC);

CREATE TRIGGER trg_profile_versions_immutable
    BEFORE UPDATE OR DELETE ON public.channel_profile_versions
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

ALTER TABLE public.channels
    ADD CONSTRAINT fk_channels_active_profile_version
    FOREIGN KEY (workspace_id, active_profile_version_id)
    REFERENCES public.channel_profile_versions(workspace_id, id)
    DEFERRABLE INITIALLY DEFERRED;

-- 5. Editorial Theme Changes (historico com data de vigencia: CH-004)
CREATE TABLE IF NOT EXISTS public.editorial_theme_changes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL,
    channel_id uuid NOT NULL,
    previous_version_id uuid NULL,
    new_version_id uuid NOT NULL,
    previous_theme text NOT NULL DEFAULT '',
    new_theme text NOT NULL,
    reason text NOT NULL DEFAULT '',
    effective_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    changed_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now()),
    CONSTRAINT fk_theme_changes_channel_ws
        FOREIGN KEY (workspace_id, channel_id)
        REFERENCES public.channels(workspace_id, id)
        ON DELETE CASCADE,
    CONSTRAINT fk_theme_changes_new_ver
        FOREIGN KEY (workspace_id, new_version_id)
        REFERENCES public.channel_profile_versions(workspace_id, id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_theme_changes_channel_date
    ON public.editorial_theme_changes (workspace_id, channel_id, effective_at DESC);

CREATE TRIGGER trg_theme_changes_immutable
    BEFORE UPDATE OR DELETE ON public.editorial_theme_changes
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

-- 6. Audit Events
CREATE TABLE IF NOT EXISTS public.audit_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES public.workspaces(id) ON DELETE CASCADE,
    actor_user_id uuid NOT NULL,
    action text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    correlation_id uuid NOT NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_audit_events_ws_created
    ON public.audit_events (workspace_id, created_at DESC);

CREATE TRIGGER trg_audit_events_immutable
    BEFORE UPDATE OR DELETE ON public.audit_events
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
