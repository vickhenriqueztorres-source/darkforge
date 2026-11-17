# Estado — DarkForge Studio UI

> Atualizado pela IDE ao fim de cada tarefa. Fonte de verdade para retomar o trabalho.

## Posição atual

- **Subplano:** UI-07 (Concluído)
- **Tarefa:** UI-07-T06 (Documentação final e aceite)
- **Status:** concluído (G-UI0 a G-UI7 verdes)
- **Último gate verde:** G-UI7

## Mapa do Repositório

- **Frontend:** Next.js `15.5.29` (App Router), React `19.0.0`, TypeScript `5.7.0`, CSS tokens em [globals.css](file:///d:/YOUTUBE%20MANAGET/apps/web/src/app/globals.css), API client em [api.ts](file:///d:/YOUTUBE%20MANAGET/apps/web/src/lib/api.ts), Supabase browser client em [supabase.ts](file:///d:/YOUTUBE%20MANAGET/apps/web/src/lib/supabase.ts), shell principal em [page.tsx](file:///d:/YOUTUBE%20MANAGET/apps/web/src/app/page.tsx), rota dedicada em [studio/page.tsx](file:///d:/YOUTUBE%20MANAGET/apps/web/src/app/studio/page.tsx), componentes em `apps/web/src/components/studio/*` e lógica em `apps/web/src/lib/studio/*`.
- **Clean plate:** `apps/web/public/studio/studio-clean-plate.{avif,webp,jpg}` (`2560x1429`, `86 KB` AVIF / `353 KB` WebP / `442 KB` JPG).
- **Backend API:** FastAPI + Pydantic v2 em [main.py](file:///d:/YOUTUBE%20MANAGET/apps/api/main.py), DI em [dependencies.py](file:///d:/YOUTUBE%20MANAGET/apps/api/dependencies.py), rotas Studio em [studio.py](file:///d:/YOUTUBE%20MANAGET/apps/api/routes/studio.py).
- **Domínio & Contratos:** [contracts.py](file:///d:/YOUTUBE%20MANAGET/core/studio/contracts.py), [registry.py](file:///d:/YOUTUBE%20MANAGET/core/studio/registry.py), [service.py](file:///d:/YOUTUBE%20MANAGET/core/studio/service.py).
- **Persistência & Worker:** [studio_repo.py](file:///d:/YOUTUBE%20MANAGET/adapters/supabase_db/studio_repo.py), [handler.py](file:///d:/YOUTUBE%20MANAGET/workers/agents/handler.py) na fila única Postgres ([0004_sp02_jobs_outbox_storage.sql](file:///d:/YOUTUBE%20MANAGET/migrations/0004_sp02_jobs_outbox_storage.sql)).
- **Migrations Studio:** [0015_studio_ui_agents.sql](file:///d:/YOUTUBE%20MANAGET/migrations/0015_studio_ui_agents.sql), [0016_studio_fix_sp01_0014_triggers.sql](file:///d:/YOUTUBE%20MANAGET/migrations/0016_studio_fix_sp01_0014_triggers.sql), [0017_studio_allow_workspace_cascade_delete.sql](file:///d:/YOUTUBE%20MANAGET/migrations/0017_studio_allow_workspace_cascade_delete.sql).

## Gates

| Gate | Status | Evidência |
|---|---|---|
| G-UI0 | DONE | `ADR-UI-001-encaixe.md`, mapa real, clean plate `2560x1429` em `apps/web/public/studio/` |
| G-UI1 | DONE | Migrations `0015`, `0016`, `0017` aplicadas no Postgres; RLS 2 workspaces + views `security_invoker` + bloqueio de insert direto pelo navegador em `test_studio_ui_live_pipeline.py` |
| G-UI2 | DONE | `test_studio_ui_live_pipeline.py` executou o fluxo completo via fila única `jobs`, fencing token stale rejeitado (`FENCING_TOKEN_STALE`), lease expirado recuperado (`attempt >= 2`), e 4 testes unitários de contratos em `test_studio_contracts_and_registry.py` |
| G-UI3 | DONE | `getStudioSnapshot`, `getStudioEvents` cursor replay sem perdas, reducer TS `applyStudioEvent` (3 suítes verdes em `run-studio-tests.mjs`), `unknown`/`stale` |
| G-UI4 | DONE | Maquete 2.5D (`StudioStage`) com 6 salas + 8 sprites, testada em `1280`, `1440`, `1920px`, `375px` mobile, `prefers-reduced-motion`, Tab/Enter/Escape no Chromium via `test_studio_ui_browser.py` |
| G-UI5 | DONE | Painéis `Canal`, `Oportunidade de Vídeo` (`Por quê?`), `Atividade dos Agentes`, `RoomDrawer` e `AgentModal` sem números fixos (`indisponível` explícito para `unknown`) |
| G-UI6 | DONE | `create_content_item` idempotente, `run/cancel/retry`, `approvals` versionado controlando handoffs, `revise_output` criando v2 humana, `update_channel_agent` com guarda de consentimento, `publish-manual` validando URL YouTube |
| G-UI7 | DONE | E2E Python + E2E Playwright Chromium + A11y teclado/foco/reduced-motion + build Next.js (`/studio` `4.67 kB`, `/` `17.6 kB`) + guia `how-to-add-agent.md` |

## Agentes por disponibilidade

| Agente | Depende de | Disponível? | Observação |
|---|---|---|---|
| dados | SP-03 | Sim | Lê `metric_snapshots` e `sync_cursors`; métricas ausentes retornam `unknown` |
| pesquisa | SP-04 | Sim | Lê `reference_videos`, `studio_video_outliers`, `google_trends_validations` |
| estrategia | SP-06, SP-07 | Sim | Usa `KnowledgeService` + `OpportunityService`; exige aprovação humana |
| titulos | SP-05 | Sim | Validação de originalidade/similaridade (`needs_review` >= 0.70) |
| roteiro | SP-06 | Sim | Usa RAG L2/L3 + perfil do canal |
| thumbnail | SP-05 | Sim | `vision_available=false` quando sem provedor de visão |
| edicao | SP-08 | Condicional (`false` sem `DARKFORGE_CORE_PATH`) | Contrato SP-08 pronto; inicia `enabled=false` com `DARKFORGE_UNAVAILABLE` quando sem executável local, habilitável por canal/teste |
| publicacao | SP-07 | Sim | Gera `publication_plan` (`requires_human_publish=true`); nunca publica |

## Decisões (ADRs)

- [ADR-UI-001-encaixe.md](file:///d:/YOUTUBE%20MANAGET/docs/studio-ui/adr/ADR-UI-001-encaixe.md)

## Divergências entre documentação e código

- `schema-reference.sql` usa `public.is_workspace_member(uuid)`; no código real os helpers estão em `app.is_workspace_member(uuid)` e `app.has_workspace_role(uuid, text[])` com `FORCE ROW LEVEL SECURITY`.
- `0014` adicionou triggers globais em `workspaces` e `channels` que conflitavam com `create_workspace_with_owner` e `create_channel_with_profile`; compatibilizado em `0016`.
- `trg_agent_events_immutable` e `trg_approvals_immutable` restringem apenas `UPDATE` (mantendo `DELETE` revogado de `authenticated`/`anon`/`PUBLIC`), permitindo `ON DELETE CASCADE` em exclusão de workspace (`0017`), seguindo o padrão de `0006`.

## Bloqueios

- `DARKFORGE_CORE_PATH` não configurado no ambiente: agente `edicao` fica desabilitado por padrão em novos canais até fornecimento do núcleo ou habilitação explícita na configuração do agente.

## Log de tarefas

| Data | Tarefa | O que mudou | Evidência | Próximo |
|---|---|---|---|---|
| 2026-11-17 | UI-00 | Mapa, inventário, `ADR-UI-001-encaixe.md` e clean plate `2560x1429` (AVIF/WebP/JPG) | `apps/web/public/studio/studio-clean-plate.*` | UI-01 |
| 2026-11-17 | UI-01 | Migrations `0015`, `0016`, `0017`, views `security_invoker`, RLS 2 workspaces | `apply_migrations.py` + `test_studio_ui_live_pipeline.py` | UI-02 |
| 2026-11-17 | UI-02 | `core/studio/{contracts,registry,service}.py`, `studio_repo.py`, `workers/agents/handler.py` | `test_studio_contracts_and_registry.py` (4/4) + `test_studio_ui_live_pipeline.py` | UI-03 |
| 2026-11-17 | UI-03 | `apps/api/routes/studio.py`, `api.ts`, `reducer.ts` com replay por cursor | `test_studio_ui_live_pipeline.py` + `run-studio-tests.mjs` | UI-04..UI-06 |
| 2026-11-17 | UI-04..UI-06 | `studio-layout.ts`, `StudioStage.tsx`, `StudioPanels.tsx`, `RoomDrawer.tsx`, `AgentModal.tsx`, `StudioWorkspace.tsx`, `/studio`, `globals.css` | `pnpm typecheck:web`, `pnpm build:web`, `test:studio` | UI-07 |
| 2026-11-17 | UI-07 | E2E Playwright Chromium (`1280/1440/1920/375px`, teclado, reduced motion), `how-to-add-agent.md` | `test_studio_ui_browser.py` PASSED | Concluído |
