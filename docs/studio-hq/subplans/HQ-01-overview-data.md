# HQ-01: Dados agregados (backend + cliente + tempo real)

**Objetivo:** entregar todos os canais do workspace com o estado dos agentes numa chamada só.
**Depende de:** HQ-00.
**Gate:** G-HQ1.

## Tarefas

### HQ-01-T01: View SQL
`migrations/0018_studio_hq_overview.sql`:
- `CREATE OR REPLACE VIEW public.v_studio_channel_overview WITH (security_invoker = true)`, uma linha por
  canal do workspace (inclusive canais **sem** agentes, via `LEFT JOIN`), com:
  `workspace_id, channel_id, display_name, handle, status, niche, agents_json` (array com
  `agent_key, room_key, status, enabled, progress` de `v_studio_agent_state`), contadores
  (`working, awaiting_human, blocked, failed, agents, disabled_agents`, mesmas regras de `v_studio_room_state`),
  `active_item_json` (item de conteúdo mais recente não publicado/arquivado, ou `null`) e `last_event_at`
  (`max(created_at)` de `agent_events` do canal).
- `GRANT SELECT ON public.v_studio_channel_overview TO authenticated;`
- Migração idempotente e com bloco de rollback comentado, no padrão das migrações existentes.

**Teste:** script SQL de verificação com 2 workspaces: usuário de um não enxerga canais do outro (RLS via `security_invoker`).

### HQ-01-T02: Repositório e serviço
- Repositório (`adapters/supabase_db/...`): `get_studio_overview(workspace_id)` lendo a view, ordenado como `listChannels`.
- `core/studio/service.py`: `get_overview(actor, workspace_id)` com `require_membership`, montando
  `totals` e `snapshot_at`. **Não** chamar `ensure_channel_agents` aqui (decisão D2).
- Avatar: ler do cache do adaptador `adapters/youtube/public_channel.py` se já existir para o canal;
  nunca fazer chamada externa nesta rota. Sem cache → `avatar_url: null`.

**Teste:** `tests/unit/test_studio_overview.py` com repositório fake: canais com e sem agentes, totais corretos,
membro de outro workspace recebe 403, nenhuma chamada ao YouTube.

### HQ-01-T03: Rota
`apps/api/routes/studio.py`: `@router.get("/overview")` com as mesmas dependências das outras rotas
(`get_current_user`, `get_workspace_id`, `get_container`, `_require_studio`).

### HQ-01-T04: Cliente
`apps/web/src/lib/api.ts`: `getStudioOverview(token, workspaceId): Promise<StudioOverview>`.

### HQ-01-T05: Hook com SWR e tempo real
`apps/web/src/lib/studio/useStudioOverview.ts`:
- `useSWR` com chave `["studio-overview", workspaceId]`, `revalidateOnFocus: true`.
- Assinar `postgres_changes` INSERT em `agent_events` com `filter: workspace_id=eq.<id>` (mesmo padrão
  do `StudioWorkspace.tsx`). A cada evento, `mutate()` com debounce de 400 ms e no máximo 1 refetch/s.
- Expor `realtimeStatus: "connected" | "reconnecting" | "polling"`; em `polling`, `refreshInterval: 15000`.
- Ação `prepareStudio(channelId)`: chama `api.getStudioSnapshot` daquele canal (que já provisiona) e depois `mutate()`.

**Teste:** unitário do debounce/limitador (sem rede).

## Gate G-HQ1
- [ ] Migração aplica limpa num banco novo e numa base existente
- [ ] `pytest` passando, incluindo `test_studio_overview.py`
- [ ] Rota responde com 0, 1 e vários canais; canal sem agentes aparece com `provisioned: false`
- [ ] Hook atualiza a tela ao receber evento, sem tempestade de requests (conferir no Network)
