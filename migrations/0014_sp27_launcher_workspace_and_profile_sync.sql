-- Migration 0014: Auto-link workspaces & channels created directly in Supabase / antidetect_launcher (SP-27)

CREATE OR REPLACE FUNCTION app.trg_ensure_workspace_owner_member()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
BEGIN
  IF NEW.created_by IS NOT NULL THEN
    INSERT INTO public.workspace_members (workspace_id, user_id, role)
    VALUES (NEW.id, NEW.created_by, 'owner')
    ON CONFLICT (workspace_id, user_id) DO NOTHING;
  END IF;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION app.trg_ensure_workspace_owner_member() FROM PUBLIC, anon;

DROP TRIGGER IF EXISTS trg_workspaces_auto_owner_member ON public.workspaces;
CREATE TRIGGER trg_workspaces_auto_owner_member
AFTER INSERT ON public.workspaces
FOR EACH ROW
EXECUTE FUNCTION app.trg_ensure_workspace_owner_member();


CREATE OR REPLACE FUNCTION app.trg_ensure_channel_default_profile()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_prof_id uuid;
BEGIN
  IF NEW.active_profile_version_id IS NULL THEN
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

REVOKE ALL ON FUNCTION app.trg_ensure_channel_default_profile() FROM PUBLIC, anon;

DROP TRIGGER IF EXISTS trg_channels_auto_default_profile ON public.channels;
CREATE TRIGGER trg_channels_auto_default_profile
AFTER INSERT ON public.channels
FOR EACH ROW
EXECUTE FUNCTION app.trg_ensure_channel_default_profile();


CREATE OR REPLACE FUNCTION public.claim_launcher_workspaces()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_uid uuid;
  v_email text;
  v_inserted integer := 0;
BEGIN
  v_uid := auth.uid();
  IF v_uid IS NULL THEN
    RETURN 0;
  END IF;

  v_email := COALESCE(auth.jwt()->>'email', '');
  -- Never auto-attach synthetic multi-tenant test users (@darkforge.invalid)
  IF v_email LIKE '%@darkforge.invalid' THEN
    RETURN 0;
  END IF;

  INSERT INTO public.workspace_members (workspace_id, user_id, role)
  SELECT w.id, v_uid, 'owner'
  FROM public.workspaces w
  WHERE w.slug = 'managet-canais-youtube'
     OR COALESCE(w.settings_json->>'source', '') = 'antidetect_launcher'
  ON CONFLICT (workspace_id, user_id) DO NOTHING;

  GET DIAGNOSTICS v_inserted = ROW_COUNT;
  RETURN v_inserted;
END;
$$;

REVOKE ALL ON FUNCTION public.claim_launcher_workspaces() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.claim_launcher_workspaces() TO authenticated, service_role;


-- Backfill existing workspaces missing owner membership (e.g., MANAGET • Canais YouTube)
INSERT INTO public.workspace_members (workspace_id, user_id, role)
SELECT w.id, w.created_by, 'owner'
FROM public.workspaces w
WHERE w.created_by IS NOT NULL
ON CONFLICT (workspace_id, user_id) DO NOTHING;


-- Backfill existing channels missing v1 profile (O Outro Lado, SOBREVIDA, MIGUEL TRADER, LUME ANCESTRAL)
DO $$
DECLARE
  r record;
  v_prof_id uuid;
BEGIN
  FOR r IN
    SELECT * FROM public.channels WHERE active_profile_version_id IS NULL
  LOOP
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
      r.workspace_id,
      r.id,
      1,
      r.display_name,
      COALESCE(r.platform, 'youtube'),
      'pt-BR',
      'BR',
      'America/Sao_Paulo',
      'Documentario & Investigacao',
      'Engenharia reversa de atencao e retencao',
      r.display_name,
      '{"persona": "audiencia principal do canal"}'::jsonb,
      jsonb_build_array(LOWER(r.display_name), 'outliers', 'retencao'),
      '{"tone": "direto, instigante e documental"}'::jsonb,
      '["long", "short"]'::jsonb,
      '["crescimento", "retencao"]'::jsonb,
      '["sem plagio"]'::jsonb,
      'Perfil inicial v1 gerado automaticamente para canal sincronizado no Supabase',
      r.created_by
    )
    ON CONFLICT (channel_id, version_number) DO UPDATE
      SET name = EXCLUDED.name
    RETURNING id INTO v_prof_id;

    UPDATE public.channels
    SET active_profile_version_id = v_prof_id
    WHERE id = r.id;
  END LOOP;
END;
$$;
