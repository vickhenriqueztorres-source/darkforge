# Estado da Sede DarkForge

Atualizar este arquivo no fim de cada subplano.

| Subplano | Status | Commit | Observações |
| --- | --- | --- | --- |
| HQ-00 Contratos | concluído | `feat(hq): contratos da Sede (HQ-00)` | G-HQ0 verde (`hq-types.ts`, `hq-status.ts`, fixtures, contrato) |
| HQ-01 Dados agregados | concluído | `feat(hq): overview agregado dos canais (HQ-01)` | G-HQ1 verde (`0018_studio_hq_overview.sql` aplicada + RLS verificado, `test_studio_overview.py`, `useStudioOverview`, `86 passed`) |
| HQ-02 Layout do prédio | concluído | `feat(hq): layout procedural do prédio (HQ-02)` | G-HQ2 verde (`layoutHQ.ts` e `hqColors.ts` puros sem React/three; `hq_layout_unit_tests: 4 suites passed`) |
| HQ-03 Módulo e letreiro | pendente | | |
| HQ-04 Bonecos em massa | pendente | | |
| HQ-05 Câmera e navegação | pendente | | |
| HQ-06 HUD e acessibilidade | pendente | | |
| HQ-07 Gate visual | pendente | | |

## Resumo da descoberta (HQ-00-T01)

- **Reaproveitamento no frontend:** `office3d/layout3d.ts` (`PALETTE`, `AGENT_LOOK`, `agentBubble`, `OUTER_WALL_HEIGHT`, `PARTITION_HEIGHT`, `DOOR_WIDTH`), `office3d/OfficeScene.tsx` (`ISO_AZIMUTH = Math.PI / 4`, `OverlaySync`, configuração de `Canvas` e sombras), `office3d/AgentFigure.tsx` (proporções e `AGENT_LOOK` para o LOD do estúdio focado), `office3d/Office3D.tsx` (`IntersectionObserver`, `usePrefersReducedMotion`), `StudioWorkspace.tsx` (assinatura Supabase Realtime em `agent_events` e chip de status), `lib/studio/types.ts` (`AgentKey`, `RoomKey`, `AgentVisualStatus`) e `lib/studio/studio-layout.ts` (`PIPELINE_ORDER`).
- **Reaproveitamento no backend:** `apps/api/routes/studio.py` (`router` `/api/v1/studio` com `get_current_user`, `get_workspace_id`, `get_container`, `_require_studio`), `core/studio/service.py` (`StudioService` com `require_membership`), `adapters/supabase_db/studio_repo.py` e `migrations/0015_studio_ui_agents.sql` (`v_studio_agent_state`, `v_studio_room_state`).
- **Regra de contagem observada:** `v_studio_room_state` conta `awaiting_human` como `needs_review` + `waiting_approval`, enquanto `Office3D.tsx` e `studioLamp` incluem também `waiting_input` como estado de espera humana; `counts` no SQL manterá a regra exata de `v_studio_room_state` e `studioLamp`/`studioAwaitingCount` no TS leem `agents` diretamente quando disponíveis.

## Decisões tomadas durante a execução

- `core/` tem teste de fronteira proibindo imports HTTP (`httpx`/`fastapi`); por isso `StudioService` receberá um lookup opcional injetado para ler o cache de avatar de `PublicChannelCollector` sem importar `adapters/youtube/public_channel.py` em `core/`.

## Pendências e desvios do plano

- `v0/estudio-canal-real-3d` possuía alterações locais não commitadas; `feat/sede-canais` foi criada a partir dela (pois `main` ainda não contém `office3d/`).
