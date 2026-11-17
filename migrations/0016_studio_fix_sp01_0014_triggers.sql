-- ============================================================================
-- Migration 0016: Compatibiliza triggers do 0014 com create_workspace_with_owner
--                 e create_channel_with_profile (SP-01 + Studio UI)
-- ============================================================================

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
    VALUES (v_workspace_id, v_user_id, 'owner')
    ON CONFLICT (workspace_id, user_id) DO NOTHING;

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

CREATE OR REPLACE FUNCTION app.trg_ensure_channel_default_profile()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_prof_id uuid;
  v_is_launcher boolean := false;
BEGIN
  SELECT (COALESCE(w.settings_json->>'source', '') = 'antidetect_launcher')
    INTO v_is_launcher
  FROM public.workspaces AS w
  WHERE w.id = NEW.workspace_id;

  IF NEW.active_profile_version_id IS NULL
     AND (NEW.external_channel_id IS NOT NULL OR COALESCE(v_is_launcher, false)) THEN
    INSERT INTO public.channel_profile_versions (
      workspace_id,
      channel_id,
      version_number,
      name,
      platform,
      language,
      country,
      timezone,
      niche,
      positioning,
      editorial_theme,
      audience_json,
      pillars_json,
      voice_json,
      formats_json,
      objectives_json,
      restrictions_json,
      change_summary,
      created_by
    )
    VALUES (
      NEW.workspace_id,
      NEW.id,
      1,
      NEW.display_name,
      COALESCE(NEW.platform, 'youtube'),
      'pt-BR',
      'BR',
      'America/Sao_Paulo',
      'Documentario & Investigacao',
      'Engenharia reversa de atencao e retencao',
      NEW.display_name,
      '{"persona": "audiencia principal do canal"}'::jsonb,
      jsonb_build_array(LOWER(NEW.display_name), 'outliers', 'retencao'),
      '{"tone": "direto, instigante e documental"}'::jsonb,
      '["long", "short"]'::jsonb,
      '["crescimento", "retencao"]'::jsonb,
      '["sem plagio"]'::jsonb,
      'Perfil inicial v1 gerado automaticamente para canal sincronizado no Supabase',
      NEW.created_by
    )
    ON CONFLICT (channel_id, version_number) DO UPDATE
      SET name = EXCLUDED.name
    RETURNING id INTO v_prof_id;

    UPDATE public.channels
    SET active_profile_version_id = v_prof_id
    WHERE id = NEW.id AND active_profile_version_id IS NULL;
  END IF;
  RETURN NEW;
END;
$$;
