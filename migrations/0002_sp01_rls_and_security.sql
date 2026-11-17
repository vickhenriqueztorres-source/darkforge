-- ============================================================================
-- Migration 0002: RLS, Grants Minimos e RPCs Security Definer Seguras
-- Subplano: SP-01 (SP-01-T04, SP-01-T05, T-SEC-001, T-SEC-002)
-- ADRs: ADR-011
-- ============================================================================

-- Helper allowlistado com search_path fixo e tabelas qualificadas
CREATE OR REPLACE FUNCTION app.is_workspace_member(target_workspace_id uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.workspace_members AS wm
        WHERE wm.workspace_id = target_workspace_id
          AND wm.user_id = auth.uid()
    );
$$;

CREATE OR REPLACE FUNCTION app.has_workspace_role(target_workspace_id uuid, allowed_roles text[])
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT EXISTS (
        SELECT 1
        FROM public.workspace_members AS wm
        WHERE wm.workspace_id = target_workspace_id
          AND wm.user_id = auth.uid()
          AND wm.role = ANY(allowed_roles)
    );
$$;

-- RPC segura para criacao atomica de workspace + membership owner
CREATE OR REPLACE FUNCTION app.create_workspace_with_owner(p_name text, p_slug text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
    v_user_id uuid := auth.uid();
    v_workspace_id uuid;
BEGIN
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Authentication required' USING ERRCODE = 'insufficient_privilege';
    END IF;

    INSERT INTO public.workspaces (name, slug, created_by)
    VALUES (trim(p_name), lower(trim(p_slug)), v_user_id)
    RETURNING id INTO v_workspace_id;

    INSERT INTO public.workspace_members (workspace_id, user_id, role)
    VALUES (v_workspace_id, v_user_id, 'owner');

    INSERT INTO public.audit_events (
        workspace_id, actor_user_id, action, entity_type, entity_id, correlation_id, metadata_json
    )
    VALUES (
        v_workspace_id, v_user_id, 'workspace.created', 'workspace', v_workspace_id,
        gen_random_uuid(), jsonb_build_object('slug', lower(trim(p_slug)))
    );

    RETURN v_workspace_id;
END;
$$;

REVOKE ALL ON SCHEMA app FROM PUBLIC;
GRANT USAGE ON SCHEMA app TO authenticated;

REVOKE ALL ON FUNCTION app.is_workspace_member(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.has_workspace_role(uuid, text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION app.create_workspace_with_owner(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.is_workspace_member(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION app.has_workspace_role(uuid, text[]) TO authenticated;
GRANT EXECUTE ON FUNCTION app.create_workspace_with_owner(text, text) TO authenticated;

-- Grants minimos nas tabelas
REVOKE ALL ON public.workspaces FROM PUBLIC, anon;
REVOKE ALL ON public.workspace_members FROM PUBLIC, anon;
REVOKE ALL ON public.channels FROM PUBLIC, anon;
REVOKE ALL ON public.channel_profile_versions FROM PUBLIC, anon;
REVOKE ALL ON public.editorial_theme_changes FROM PUBLIC, anon;
REVOKE ALL ON public.audit_events FROM PUBLIC, anon;

GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspaces TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.workspace_members TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.channels TO authenticated;
GRANT SELECT, INSERT ON public.channel_profile_versions TO authenticated;
GRANT SELECT, INSERT ON public.editorial_theme_changes TO authenticated;
GRANT SELECT, INSERT ON public.audit_events TO authenticated;

-- Habilitar e forcar RLS em todas as tabelas
ALTER TABLE public.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspaces FORCE ROW LEVEL SECURITY;

ALTER TABLE public.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workspace_members FORCE ROW LEVEL SECURITY;

ALTER TABLE public.channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.channels FORCE ROW LEVEL SECURITY;

ALTER TABLE public.channel_profile_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.channel_profile_versions FORCE ROW LEVEL SECURITY;

ALTER TABLE public.editorial_theme_changes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.editorial_theme_changes FORCE ROW LEVEL SECURITY;

ALTER TABLE public.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_events FORCE ROW LEVEL SECURITY;

-- Policies: workspaces
CREATE POLICY workspaces_select_member ON public.workspaces
    FOR SELECT TO authenticated
    USING (app.is_workspace_member(id));

CREATE POLICY workspaces_insert_creator ON public.workspaces
    FOR INSERT TO authenticated
    WITH CHECK (created_by = auth.uid());

CREATE POLICY workspaces_update_owner ON public.workspaces
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(id, ARRAY['owner']))
    WITH CHECK (app.has_workspace_role(id, ARRAY['owner']));

CREATE POLICY workspaces_delete_owner ON public.workspaces
    FOR DELETE TO authenticated
    USING (app.has_workspace_role(id, ARRAY['owner']));

-- Policies: workspace_members
CREATE POLICY workspace_members_select_member ON public.workspace_members
    FOR SELECT TO authenticated
    USING (app.is_workspace_member(workspace_id));

CREATE POLICY workspace_members_insert_owner ON public.workspace_members
    FOR INSERT TO authenticated
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner']));

CREATE POLICY workspace_members_update_owner ON public.workspace_members
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner']));

CREATE POLICY workspace_members_delete_owner ON public.workspace_members
    FOR DELETE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner']));

-- Policies: channels
CREATE POLICY channels_select_member ON public.channels
    FOR SELECT TO authenticated
    USING (app.is_workspace_member(workspace_id));

CREATE POLICY channels_insert_editor ON public.channels
    FOR INSERT TO authenticated
    WITH CHECK (
        app.has_workspace_role(workspace_id, ARRAY['owner', 'editor'])
        AND created_by = auth.uid()
    );

CREATE POLICY channels_update_editor ON public.channels
    FOR UPDATE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']))
    WITH CHECK (app.has_workspace_role(workspace_id, ARRAY['owner', 'editor']));

CREATE POLICY channels_delete_owner ON public.channels
    FOR DELETE TO authenticated
    USING (app.has_workspace_role(workspace_id, ARRAY['owner']));

-- Policies: channel_profile_versions (append-only; valida relacao pai-filho)
CREATE POLICY profile_versions_select_member ON public.channel_profile_versions
    FOR SELECT TO authenticated
    USING (
        app.is_workspace_member(workspace_id)
        AND EXISTS (
            SELECT 1 FROM public.channels AS c
            WHERE c.id = channel_id AND c.workspace_id = channel_profile_versions.workspace_id
        )
    );

CREATE POLICY profile_versions_insert_editor ON public.channel_profile_versions
    FOR INSERT TO authenticated
    WITH CHECK (
        app.has_workspace_role(workspace_id, ARRAY['owner', 'editor'])
        AND created_by = auth.uid()
        AND EXISTS (
            SELECT 1 FROM public.channels AS c
            WHERE c.id = channel_id AND c.workspace_id = channel_profile_versions.workspace_id
        )
    );

-- Policies: editorial_theme_changes (append-only; valida relacao pai-filho)
CREATE POLICY theme_changes_select_member ON public.editorial_theme_changes
    FOR SELECT TO authenticated
    USING (
        app.is_workspace_member(workspace_id)
        AND EXISTS (
            SELECT 1 FROM public.channels AS c
            WHERE c.id = channel_id AND c.workspace_id = editorial_theme_changes.workspace_id
        )
    );

CREATE POLICY theme_changes_insert_editor ON public.editorial_theme_changes
    FOR INSERT TO authenticated
    WITH CHECK (
        app.has_workspace_role(workspace_id, ARRAY['owner', 'editor'])
        AND changed_by = auth.uid()
        AND EXISTS (
            SELECT 1 FROM public.channels AS c
            WHERE c.id = channel_id AND c.workspace_id = editorial_theme_changes.workspace_id
        )
    );

-- Policies: audit_events (append-only)
CREATE POLICY audit_events_select_member ON public.audit_events
    FOR SELECT TO authenticated
    USING (app.is_workspace_member(workspace_id));

CREATE POLICY audit_events_insert_member ON public.audit_events
    FOR INSERT TO authenticated
    WITH CHECK (
        app.is_workspace_member(workspace_id)
        AND actor_user_id = auth.uid()
    );
