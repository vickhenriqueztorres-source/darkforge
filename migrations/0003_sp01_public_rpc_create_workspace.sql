-- ============================================================================
-- Migration 0003: Expor RPC segura create_workspace_with_owner no schema public
-- Motivo: PostgREST expoe por padrao apenas public e graphql_public (PGRST106)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.create_workspace_with_owner(p_name text, p_slug text)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, app
AS $$
BEGIN
    RETURN app.create_workspace_with_owner(p_name, p_slug);
END;
$$;

REVOKE ALL ON FUNCTION public.create_workspace_with_owner(text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.create_workspace_with_owner(text, text) TO authenticated;
