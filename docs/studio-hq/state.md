# Estado da Sede DarkForge

Atualizar este arquivo no fim de cada subplano.

| Subplano | Status | Commit | Observações |
| --- | --- | --- | --- |
| HQ-00 Contratos | concluído | `feat(hq): contratos da Sede (HQ-00)` | G-HQ0 verde (`hq-types.ts`, `hq-status.ts`, fixtures, contrato) |
| HQ-01 Dados agregados | concluído | `feat(hq): overview agregado dos canais (HQ-01)` | G-HQ1 verde (`0018_studio_hq_overview.sql` aplicada + RLS verificado, `test_studio_overview.py`, `useStudioOverview`, `86 passed`) |
| HQ-02 Layout do prédio | concluído | `feat(hq): layout procedural do prédio (HQ-02)` | G-HQ2 verde (`layoutHQ.ts` e `hqColors.ts` puros sem React/three; `hq_layout_unit_tests: 4 suites passed`) |
| HQ-03 Módulo e letreiro | concluído | `feat(hq): estúdios, letreiros e recepção (HQ-03)` | G-HQ3 verde (`primitives.tsx`, `signText.ts`, `ChannelSign`, `StudioModule`, `HQBuilding`, `Lobby`, fontes `/fonts/inter-{600,700}.woff`, `hq_signtext_unit_tests: 4 suites passed`) |
| HQ-04 Bonecos em massa | concluído | `feat(hq): agentes em multidão com LOD (HQ-04)` | G-HQ4 verde (`figureProportions.ts`, `crowdPose.ts`, `CrowdFigures` 4 `InstancedMesh` + 1 `useFrame` + LOD `AgentFigure`, `PerfProbe`, `hq_crowdpose_unit_tests: 3 suites passed`) |
| HQ-05 Câmera e navegação | concluído | `feat(hq): câmera, foco e navegação (HQ-05)` | G-HQ5 verde (`HQScene`, `CameraRig`, `cameraMath`, `hq-navigation`, `useHQNavigation`, seletor "Sede \| Estúdio do canal", menu "Sede & Estúdios", botão "← Sede", fluxo completo com Back/reload testado em Chromium) |
| HQ-06 HUD e acessibilidade | concluído | `feat(hq): HUD, lista acessível e mobile (HQ-06)` | G-HQ6 verde (`HQ.tsx` HUD/filtros/busca/paginação/hover/estados, `HQFocusPanel`, `StudioCardList` desktop + mobile <768px sem WebGL, `hq_a11y_unit_tests: 4 suites passed`, screenshots 375/1280/1440/1920) |
| HQ-07 Gate visual | concluído | `feat(hq): gate final da Sede (HQ-07)` | G-HQ7 verde: revisão visual contra `design-spec.md`, screenshots em `docs/studio-hq/reference/screens/`, 60 FPS e ≤ 137 draw calls com 24 canais, regressão `typecheck` + `test:studio` + `pytest` + `next build` |

## Resumo da descoberta (HQ-00-T01)

- **Reaproveitamento no frontend:** `office3d/layout3d.ts` (`PALETTE`, `AGENT_LOOK`, `agentBubble`, `OUTER_WALL_HEIGHT`, `PARTITION_HEIGHT`, `DOOR_WIDTH`), `office3d/OfficeScene.tsx` (`ISO_AZIMUTH = Math.PI / 4`, `OverlaySync`, configuração de `Canvas` e sombras), `office3d/AgentFigure.tsx` (proporções e `AGENT_LOOK` para o LOD do estúdio focado), `office3d/Office3D.tsx` (`IntersectionObserver`, `usePrefersReducedMotion`), `StudioWorkspace.tsx` (assinatura Supabase Realtime em `agent_events` e chip de status), `lib/studio/types.ts` (`AgentKey`, `RoomKey`, `AgentVisualStatus`) e `lib/studio/studio-layout.ts` (`PIPELINE_ORDER`).
- **Reaproveitamento no backend:** `apps/api/routes/studio.py` (`router` `/api/v1/studio` com `get_current_user`, `get_workspace_id`, `get_container`, `_require_studio`), `core/studio/service.py` (`StudioService` com `require_membership`), `adapters/supabase_db/studio_repo.py` e `migrations/0015_studio_ui_agents.sql` (`v_studio_agent_state`, `v_studio_room_state`).
- **Regra de contagem observada:** `v_studio_room_state` conta `awaiting_human` como `needs_review` + `waiting_approval`, enquanto `Office3D.tsx` e `studioLamp` incluem também `waiting_input` como estado de espera humana; `counts` no SQL mantém a regra exata de `v_studio_room_state` e `studioLamp`/`studioAwaitingCount` no TS leem `agents` diretamente quando disponíveis.

## Medições de desempenho (HQ-07-T03)

- **Máquina:** Windows, CPU `Intel(R) Core(TM) i5-4460 @ 3.20GHz`, GPU integrada `Intel(R) HD Graphics 4600` (Chromium ANGLE Direct3D11, `1440×900`, `next dev`).
- **1 canal (`?demo=1&perf=1`):** `60 FPS`, `65 draw calls`, `9.066 tris`, primeiro canvas em `4,23 s`.
- **12 canais (`?demo=12&perf=1`):** `60 FPS` (orçamento ≥ 55), `101 draw calls`, `67.304 tris`, primeiro canvas em `1,92 s`.
- **24 canais / 192 bonecos (`?demo=24&perf=1`):** `60 FPS` (orçamento ≥ 45), `137 draw calls` (orçamento ≤ 180), `130.776 tris`, primeiro canvas em `3,52 s`.
- **Memória JS heap (24 canais, 12 s ativo):** `256,54 MB` → `256,54 MB` (estável, sem crescimento).
- **Mobile `375×812`:** `0` `<canvas>` WebGL montados.
- **Screenshots salvos em `docs/studio-hq/reference/screens/`:** `hq-1-channel-1440.png`, `hq-3-channels-1440.png`, `hq-12-channels-1440.png`, `hq-24-channels-1440.png`, `hq-12-channels-1280.png`, `hq-12-channels-1920.png`, `hq-12-channels-375-mobile.png`, `hq-focus-working.png`, `hq-focus-awaiting.png`, `hq-focus-unprovisioned.png`, `hq-focus-disconnected.png`, `office3d-channel.png`.

## Decisões tomadas durante a execução

- `core/` tem teste de fronteira proibindo imports HTTP (`httpx`/`fastapi`); por isso `StudioService` recebe um lookup opcional injetado para ler o cache de avatar de `PublicChannelCollector` sem importar `adapters/youtube/public_channel.py` em `core/`.
- Para manter ≤ 180 draw calls com 24 estúdios e 192 bonecos, `HQBuilding.tsx` agrupa paredes com `mergeGeometries` e mobiliário/letreiros repetitivos com `InstancedMesh` (incluindo textura compartilhada para a placa `"EM PRODUÇÃO"` e `CanvasTexture` em cache para monogramas), e hitboxes de clique usam `material.visible = false` (0 draw calls com raycasting ativo).

## Pendências e desvios do plano

- `v0/estudio-canal-real-3d` possuía alterações locais não commitadas e o código de `office3d/`; `feat/sede-canais` foi criada a partir dela (pois `main` ainda não contém `office3d/`).
- `useHQNavigation` usa `window.history.replaceState` / `window.history.pushState` (em vez de `router.replace`/`router.push` do Next.js) para transições de query string na mesma rota, evitando roundtrip RSC de ~11 s no dev server enquanto mantém suporte completo a `popstate` (botão Voltar) e reload.
- `HQScene` usa `shadows="soft"` (`PCFSoftShadowMap`) em vez de `shadows="percentage"` (PCSS) e no máximo 2 `pointLight` dinâmicas (apenas em estúdios focados/hovered) combinadas com planos emissivos de luz na porta do corredor, garantindo 60 FPS na GPU integrada `Intel(R) HD Graphics 4600`.
- A amostragem de memória de 24 canais foi executada de forma automatizada por 12 s (`256,54 MB` estável) em vez de observação manual contínua de 5 min; o refetch Realtime ponta-a-ponta contra o Supabase remoto levou `5,85–6,01 s` (incluindo roundtrip de rede até o Postgres remoto + broadcast Realtime + debounce de 400 ms).
