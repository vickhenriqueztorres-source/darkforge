# HQ-04: Bonecos em multidão

**Objetivo:** colocar os 8 agentes de cada canal trabalhando dentro do seu estúdio, com até 192 bonecos a 45+ FPS.
**Depende de:** HQ-02 (e HQ-03 para ver no lugar).
**Referência:** `design-spec.md` §6.
**Gate:** G-HQ4.

## Tarefas

### HQ-04-T01: Geometria do boneco simplificado
Extrair as proporções do `office3d/AgentFigure.tsx` (altura, cabeça, tronco, pernas) para constantes compartilhadas
em `office3d/figureProportions.ts`, usadas pelos dois componentes, para o boneco da Sede ser o mesmo personagem.
Boneco da Sede = 4 partes: pernas, tronco (camisa), cabeça (pele), cabelo.

### HQ-04-T02: `CrowdFigures.tsx`
- 4 `InstancedMesh` (uma por parte), `count = canais × 8`, cor por instância (`setColorAt`) a partir de `AGENT_LOOK`.
- Posição base: `deskForAgent(slot, agentKey)` sentado; estados de aprovação → posição em volta da mesa de pauta (`slot.meeting`).
- **Um único `useFrame`** atualiza todas as matrizes: respiração, digitação, cabeça baixa, pulo do `done`,
  com fase por instância (`hash(channelId + agentKey)`), conforme a tabela do `design-spec.md` §6.
- Transição entre mesa e mesa de pauta: caminhada curta (`routeInStudio`) a 1,7 u/s, interpolada no mesmo `useFrame`.
- `disabled` → escala 0 (cadeira vazia).
- Só marcar `instanceMatrix.needsUpdate` quando algo mudou; com nenhum agente animando, não atualizar.
- Respeitar `reducedMotion`: só pose final.

### HQ-04-T03: Balões agregados
Na Sede **não** há balão por boneco. Por estúdio, no máximo 1 balão DOM acima do grupo:
"! Aguardando você" (laranja) ou "Falhou" (vermelho), seguindo a prioridade de `studioLamp`.
Posicionar com o mesmo mecanismo de `OverlaySync` do Office3D (âncoras DOM projetadas a cada frame).

### HQ-04-T04: LOD do estúdio em foco
Quando um estúdio está em foco (HQ-05), esconder as instâncias daquele canal (escala 0) e renderizar ali os
8 `AgentFigure` completos, com nome no hover e balões individuais (`agentBubble`). Reaproveitar `AgentFigure`
passando `desk` e `meeting` do `StudioSlot` (adaptar as props se necessário, sem mudar o comportamento no Office3D).

### HQ-04-T05: Medição
Componente de dev `PerfProbe` (só em `NODE_ENV=development` e com `?perf=1`) mostrando FPS e
`renderer.info.render.calls`. Registrar os números em `state.md`.

## Testes
- Unitário: `figurePose(status, t, phase)` devolve pose determinística por status (sem three).
- Unitário: mapeamento status → posição (mesa ou mesa de pauta).

## Gate G-HQ4
- [ ] 24 canais × 8 agentes renderizando, todos os status com pose distinta
- [ ] ≥ 45 FPS com 24 canais e ≥ 55 FPS com 12, a 1440p (anotar máquina em `state.md`)
- [ ] ≤ 180 draw calls com 24 canais
- [ ] Office3D atual sem mudança visual (comparar screenshot) e testes do studio passando
