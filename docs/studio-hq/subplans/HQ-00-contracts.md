# HQ-00: Descoberta e contratos

**Objetivo:** fixar o contrato de dados da Sede, os tipos e os dados de teste antes de qualquer tela.
**Depende de:** nada.
**Gate:** G-HQ0.

## Tarefas

### HQ-00-T01: Leitura obrigatória
Ler e resumir em `state.md` (5 a 10 linhas): `office3d/layout3d.ts`, `office3d/OfficeScene.tsx`,
`office3d/AgentFigure.tsx`, `office3d/Office3D.tsx`, `StudioWorkspace.tsx`, `lib/studio/types.ts`,
`apps/api/routes/studio.py`, `core/studio/service.py` e a view `v_studio_agent_state` em
`migrations/0015_studio_ui_agents.sql`. Anotar o que será reaproveitado.

### HQ-00-T02: Tipos do overview
Criar `apps/web/src/lib/studio/hq-types.ts` com `StudioOverview`, `StudioOverviewChannel`,
`StudioOverviewAgent` e `HQFilter = "all" | "working" | "awaiting" | "problem" | "unprovisioned"`,
exatamente como em `plan.md` §5. Reusar `AgentKey`, `RoomKey`, `AgentVisualStatus` de `types.ts` (não duplicar).

### HQ-00-T03: Funções puras de estado do estúdio
Em `apps/web/src/lib/studio/hq-status.ts`:
- `studioLamp(channel): "ok" | "working" | "awaiting" | "problem" | "off"` com a prioridade
  vermelho > aguardando > trabalhando > ok; `off` quando `provisioned = false` ou canal desconectado.
- `matchesFilter(channel, filter): boolean`.
- `studioSummaryText(channel): string` (texto para `aria-label` e cartão, ex.: "O Outro Lado, 2 trabalhando, 1 aguardando você").

**Teste:** tabela de casos cobrindo todos os `AgentVisualStatus`, agentes desligados, canal sem agentes.

### HQ-00-T04: Fixtures
`apps/web/src/lib/studio/__fixtures__/hq-overview.ts` com cenários de 0, 1, 3, 7, 12, 13 e 24 canais,
incluindo nomes longos (40+ caracteres), nome com acento e emoji, canal sem avatar, canal sem agentes,
canal desconectado e todos os status. Usado só em testes e no modo de demonstração de desenvolvimento.

### HQ-00-T05: Contrato do backend
Documentar em `docs/api/contracts.md` a rota `GET /api/v1/studio/overview` (cabeçalho de workspace,
resposta, erros 401/403/404 iguais às rotas do studio).

## Gate G-HQ0
- [ ] `hq-types.ts`, `hq-status.ts` e fixtures criados
- [ ] Testes de `hq-status` passando (`pnpm --filter @darkforge/web test:studio`)
- [ ] `pnpm typecheck:web` sem erros
- [ ] Contrato documentado e `state.md` atualizado
