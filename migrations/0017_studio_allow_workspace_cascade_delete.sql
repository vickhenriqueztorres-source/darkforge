-- ============================================================================
-- Migration 0017: Permitir ON DELETE CASCADE de workspace em agent_events e approvals
-- Mantem UPDATE proibido e DELETE revogado para authenticated/anon/PUBLIC (padrao 0006).
-- ============================================================================

DROP TRIGGER IF EXISTS trg_agent_events_immutable ON public.agent_events;
CREATE TRIGGER trg_agent_events_immutable
    BEFORE UPDATE ON public.agent_events
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();

DROP TRIGGER IF EXISTS trg_approvals_immutable ON public.approvals;
CREATE TRIGGER trg_approvals_immutable
    BEFORE UPDATE ON public.approvals
    FOR EACH ROW EXECUTE FUNCTION app.forbid_mutation();
