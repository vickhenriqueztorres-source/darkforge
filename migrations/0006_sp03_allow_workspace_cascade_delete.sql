-- ============================================================================
-- Migration 0006: Permitir ON DELETE CASCADE de workspace em tabelas imutaveis
-- Mantem UPDATE proibido e DELETE revogado para authenticated/anon/PUBLIC.
-- ============================================================================

DROP TRIGGER IF EXISTS trg_profile_versions_immutable ON public.channel_profile_versions;
CREATE TRIGGER trg_profile_versions_immutable
    BEFORE UPDATE ON public.channel_profile_versions
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

DROP TRIGGER IF EXISTS trg_theme_changes_immutable ON public.editorial_theme_changes;
CREATE TRIGGER trg_theme_changes_immutable
    BEFORE UPDATE ON public.editorial_theme_changes
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

DROP TRIGGER IF EXISTS trg_audit_events_immutable ON public.audit_events;
CREATE TRIGGER trg_audit_events_immutable
    BEFORE UPDATE ON public.audit_events
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
