# HQ-02: Layout procedural do prédio

**Objetivo:** uma função pura que, dado o número de canais, devolve toda a geometria do prédio.
**Depende de:** HQ-00.
**Gate:** G-HQ2.

## Tarefas

### HQ-02-T01: Constantes e tipos
`apps/web/src/components/studio/hq/layoutHQ.ts`, mesmo estilo de `office3d/layout3d.ts` (tuplas `XZ`, sem React):
- `MODULE = { w: 8.4, d: 7 }`, `CORRIDOR_W = 3.2`, `LOBBY_D = 6`, `WING_GAP = 4`, `MAX_PER_SIDE = 6`, `MAX_CHANNELS = 24`.
- `interface StudioSlot { channelId; index; wing; side: "north" | "south"; x0; x1; z0; z1; door: { inner: XZ; outer: XZ }; sign: { pos: [x,y,z]; rotationY } ; lamp: [x,y,z]; onAir: [x,y,z]; desks: DeskSlot[8]; meeting: Array<{pos: XZ; facing}>; plant: XZ; rug: {x0,x1,z0,z1} }`.
- `interface BuildingLayout { slots: StudioSlot[]; lobby: {...}; corridors: Array<{x0,x1,z0,z1}>; bounds: {x0,x1,z0,z1}; walls: Array<{axis, at, from, to, height, gaps}> }`.

### HQ-02-T02: `buildHQLayout(channelIds: string[]): BuildingLayout`
- Até 12 canais: 1 ala. Distribuição alternada norte/sul (canal 1 norte, 2 sul, 3 norte...) para o corredor
  ficar equilibrado; colunas = `ceil(n / 2)`.
- 13 a 24: 2 alas paralelas em Z, ligadas por um hall na ponta da recepção.
- Mais de 24: usar só os 24 primeiros e devolver `overflow: number` para o HUD paginar.
- Porta de cada estúdio centralizada na parede do corredor; letreiro centrado acima da porta, virado para
  o corredor (`rotationY` 0 ou π); lâmpada à direita do letreiro; placa "EM PRODUÇÃO" acima.
- 8 mesas em 2 fileiras de 4 viradas para a parede do fundo (as cadeiras ficam do lado do corredor, para
  a câmera ver o rosto/frente dos bonecos), mesa de pauta redonda no fundo, planta no canto do fundo esquerdo.
- `deskForAgent(slot, agentKey)` usando `PIPELINE_ORDER` para a ordem fixa dos agentes.
- `routeInStudio(slot, from, to)`: caminho simples dentro do estúdio (mesa ↔ mesa de pauta), desviando da mesa redonda
  (reaproveitar a ideia de `avoidTable` do `layout3d.ts`).

### HQ-02-T03: Cor do canal
`hqColors.ts`: `HQ_CHANNEL_COLORS` (8 tons do `design-spec.md` §2) e
`assignChannelColors(channelIds): Map<string, string>` determinístico, sem vizinhos iguais no mesmo lado do corredor.

## Testes (`apps/web/src/components/studio/hq/__tests__/layoutHQ.test.ts`)
- Para n = 1, 2, 3, 7, 12, 13, 24 e 30: quantidade de slots, `overflow`, nenhuma sobreposição entre estúdios,
  todos os estúdios dentro de `bounds`, toda porta tocando o corredor.
- Cada estúdio tem 8 mesas dentro dele e sem sobreposição.
- Letreiro sempre do lado do corredor e virado para ele.
- Mesmo input → mesmo output (determinístico); trocar a ordem dos ids troca só a posição, não a geometria.
- `assignChannelColors` nunca repete cor em vizinhos do mesmo lado.

## Gate G-HQ2
- [ ] `layoutHQ.ts` e `hqColors.ts` sem imports de React/three
- [ ] Todos os testes acima passando
- [ ] `pnpm typecheck:web` sem erros
