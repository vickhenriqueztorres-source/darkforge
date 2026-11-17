-- ============================================================================
-- Migration 0018: DarkForge Sede — View agregada de overview de canais
-- Subplano: HQ-01 (HQ-01-T01)
-- Referencia: docs/studio-hq/subplans/HQ-01-overview-data.md
-- ============================================================================

CREATE OR REPLACE VIEW public.v_studio_channel_overview
WITH (security_invoker = true) AS
SELECT
    c.workspace_id,
    c.id AS channel_id,
    c.display_name,
    c.handle,
    c.status,
    c.external_channel_id,
    c.created_at,
    pv.niche,
    COALESCE(
        jsonb_agg(
            jsonb_build_object(
                'agent_key', s.agent_key,
                'room_key', s.room_key,
                'status', s.status,
                'enabled', s.enabled,
                'progress', s.progress
            )
            ORDER BY s.agent_key
        ) FILTER (WHERE s.channel_agent_id IS NOT NULL),
        '[]'::jsonb
    ) AS agents_json,
    COUNT(s.channel_agent_id) FILTER (WHERE s.enabled AND s.status = 'working') AS working,
    COUNT(s.channel_agent_id) FILTER (WHERE s.enabled AND s.status IN ('needs_review', 'waiting_approval')) AS awaiting_human,
    COUNT(s.channel_agent_id) FILTER (WHERE s.enabled AND s.status IN ('blocked', 'no_signal')) AS blocked,
    COUNT(s.channel_agent_id) FILTER (WHERE s.enabled AND s.status = 'failed') AS failed,
    COUNT(s.channel_agent_id) FILTER (WHERE s.enabled) AS agents,
    COUNT(s.channel_agent_id) FILTER (WHERE NOT s.enabled) AS disabled_agents,
    (
        SELECT jsonb_build_object(
            'id', ci.id,
            'working_title', ci.working_title,
            'stage', ci.stage
        )
        FROM public.content_items AS ci
        WHERE ci.workspace_id = c.workspace_id
          AND ci.channel_id = c.id
          AND ci.stage NOT IN ('publicado_manual', 'arquivado')
          AND ci.status <> 'arquivado'
        ORDER BY ci.updated_at DESC
        LIMIT 1
    ) AS active_item_json,
    (
        SELECT MAX(ae.created_at)
        FROM public.agent_events AS ae
        WHERE ae.workspace_id = c.workspace_id
          AND ae.channel_id = c.id
    ) AS last_event_at
FROM public.channels AS c
LEFT JOIN public.channel_profile_versions AS pv
  ON pv.id = c.active_profile_version_id
 AND pv.workspace_id = c.workspace_id
LEFT JOIN public.v_studio_agent_state AS s
  ON s.workspace_id = c.workspace_id
 AND s.channel_id = c.id
GROUP BY
    c.workspace_id,
    c.id,
    c.display_name,
    c.handle,
    c.status,
    c.external_channel_id,
    c.created_at,
    pv.niche;

REVOKE ALL ON public.v_studio_channel_overview FROM PUBLIC, anon;
GRANT SELECT ON public.v_studio_channel_overview TO authenticated;

-- ============================================================================
-- Rollback:
-- REVOKE ALL ON public.v_studio_channel_overview FROM authenticated;
-- DROP VIEW IF EXISTS public.v_studio_channel_overview;
-- ============================================================================
