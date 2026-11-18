# Prompts: Sede DarkForge

Cole o **Prompt geral** uma vez. Depois cole os prompts **HQ-00 a HQ-07 em ordem**, um por vez.
Só mande o próximo quando a IA mostrar o gate do anterior marcado e as checagens passando.

---

## Prompt geral (colar primeiro)

```
Você é um engenheiro sênior de front-end 3D (React Three Fiber) e full-stack, trabalhando no
repositório DarkForge (Next.js 15 em apps/web, FastAPI em apps/api, Supabase/Postgres em migrations/).

Vamos construir a "Sede DarkForge": uma visão geral 3D isométrica onde CADA CANAL do workspace é um
ESTÚDIO (uma sala) dentro de um prédio, com o NOME DO CANAL num letreiro iluminado DO LADO DE FORA,
em cima da porta, e os 8 bonecos dos agentes daquele canal trabalhando lá dentro em tempo real.
Clicar num estúdio foca nele; "Entrar no estúdio" abre o escritório 3D do canal que já existe
(apps/web/src/components/studio/office3d/).

Documentação da tarefa (leia TUDO antes de codar e siga à risca):
- docs/studio-hq/README.md
- docs/studio-hq/plan.md            (decisões D1–D10, arquitetura, contrato, orçamento de desempenho)
- docs/studio-hq/design-spec.md     (direção de arte: é a lei visual)
- docs/studio-hq/subplans/HQ-00 … HQ-07
- docs/studio-hq/reference/sede-conceito.png (referência de clima; os nomes nos letreiros vêm dos dados)
- docs/studio-hq/state.md           (você atualiza no fim de cada subplano)

Regras:
1. Trabalhe na branch feat/sede-canais. Um subplano por vez, na ordem que eu mandar. 1 commit por subplano.
2. Reaproveite o que existe: layout3d.ts (PALETTE, AGENT_LOOK, agentBubble, PIPELINE_ORDER), AgentFigure,
   OverlaySync, o padrão de IntersectionObserver e prefers-reduced-motion do Office3D, o Realtime de
   agent_events do StudioWorkspace. Não reescreva o Office3D e não mude o visual dele.
3. Zero dados falsos na tela. Fixtures só em testes e no modo demo de desenvolvimento.
4. Funções de geometria e status são puras (sem React/three) e têm testes.
5. Acessibilidade: tudo que a cena 3D mostra também existe no DOM, navegável por teclado; status nunca só por cor.
6. Respeite o orçamento de desempenho do plan.md §8 (InstancedMesh para a multidão, 1 useFrame, frameloop demand).
7. Ao terminar cada subplano: rode pnpm typecheck:web, pnpm --filter @darkforge/web test:studio e pytest
   (quando mexer no backend), mostre o gate marcado item por item, atualize docs/studio-hq/state.md e faça o commit.
8. Se algo do plano não fizer sentido no código real, pare, explique o conflito e proponha a alternativa
   antes de seguir. Registre o desvio em state.md.

Confirme que leu a documentação respondendo com: (a) um resumo de 5 linhas do que vai construir,
(b) os arquivos existentes que vai reaproveitar, (c) dúvidas bloqueantes, se houver. Não escreva código ainda.
```

---

## HQ-00: Contratos

```
Execute o subplano docs/studio-hq/subplans/HQ-00-contracts.md (tarefas T01 a T05).

Entregas: apps/web/src/lib/studio/hq-types.ts, apps/web/src/lib/studio/hq-status.ts (studioLamp,
matchesFilter, studioSummaryText), apps/web/src/lib/studio/__fixtures__/hq-overview.ts (0, 1, 3, 7, 12,
13 e 24 canais, nomes longos, acentos, emoji, sem avatar, sem agentes, desconectado, todos os status),
testes de hq-status e o contrato da rota GET /api/v1/studio/overview em docs/api/contracts.md.

Reuse AgentKey, RoomKey e AgentVisualStatus de lib/studio/types.ts. A prioridade da lâmpada é
vermelho (failed/blocked/no_signal) > aguardando você (waiting_approval/needs_review/waiting_input) >
trabalhando > ok; "off" quando não há agentes ou o canal está desconectado.

No fim: mostre o gate G-HQ0 marcado, atualize state.md e faça o commit "feat(hq): contratos da Sede (HQ-00)".
```

## HQ-01: Dados agregados

```
Execute docs/studio-hq/subplans/HQ-01-overview-data.md (T01 a T05).

1. migrations/0018_studio_hq_overview.sql: view v_studio_channel_overview com security_invoker = true,
   LEFT JOIN para incluir canais sem agentes, agents_json, contadores com as mesmas regras de
   v_studio_room_state, active_item_json e last_event_at. GRANT SELECT para authenticated. Idempotente.
2. Repositório get_studio_overview + core/studio/service.py get_overview com require_membership.
   NÃO chame ensure_channel_agents (decisão D2). Avatar só do cache de adapters/youtube/public_channel.py,
   nunca chamada externa nesta rota.
3. GET /api/v1/studio/overview em apps/api/routes/studio.py, com as mesmas dependências das outras rotas.
4. api.getStudioOverview em apps/web/src/lib/api.ts.
5. Hook useStudioOverview com SWR + Realtime em agent_events filtrado por workspace_id, debounce 400 ms,
   no máximo 1 refetch por segundo, fallback de polling 15 s, e prepareStudio(channelId) via getStudioSnapshot.

Testes: tests/unit/test_studio_overview.py (com/sem agentes, totais, 403 de outro workspace, nenhuma chamada
ao YouTube) e teste do limitador do hook. Mostre o gate G-HQ1, atualize state.md e faça o commit
"feat(hq): overview agregado dos canais (HQ-01)".
```

## HQ-02: Layout do prédio

```
Execute docs/studio-hq/subplans/HQ-02-building-layout.md (T01 a T03).

Crie apps/web/src/components/studio/hq/layoutHQ.ts e hqColors.ts como funções PURAS (sem React/three),
no mesmo estilo de office3d/layout3d.ts. buildHQLayout(channelIds) gera: corredor central com estúdios
dos dois lados (alternando norte/sul), até 6 por lado e 12 por ala, segunda ala de 13 a 24, overflow acima
de 24; recepção na entrada; para cada estúdio: porta no corredor, letreiro centrado acima da porta virado
para o corredor, lâmpada à direita, placa "EM PRODUÇÃO" acima, 8 mesas em 2 fileiras de 4 (cadeiras do lado
do corredor), mesa de pauta redonda no fundo, planta e tapete. Use as medidas do design-spec.md §5 e a mesma
escala de mundo do Office3D.

Escreva todos os testes listados no subplano (n = 1, 2, 3, 7, 12, 13, 24, 30; sem sobreposição; portas no corredor;
determinismo; cores sem vizinhos iguais). Mostre o gate G-HQ2, atualize state.md e faça o commit
"feat(hq): layout procedural do prédio (HQ-02)".
```

## HQ-03: Estúdio, letreiro e recepção

```
Execute docs/studio-hq/subplans/HQ-03-studio-module.md (T01 a T05), seguindo design-spec.md §4 e §5
e o clima de reference/sede-conceito.png.

A peça mais importante é o ChannelSign: caixa de luz clara com leve emissive, faixa na cor do canal,
disco com o avatar (ou monograma com as iniciais), o NOME DO CANAL com drei <Text> e fonte local em
apps/web/public/fonts (a mesma família do app), auto-ajuste de tamanho para caber em 1 linha e reticências
como último recurso, texto escuro sobre a face clara. Lâmpada de status ao lado e "EM PRODUÇÃO" acima.

Implemente todos os estados do estúdio (normal, trabalhando, aguardando você, problema, em obras, desconectado,
esmaecido por filtro). Se precisar dos helpers de parede/piso do OfficeRooms, extraia para office3d/primitives.tsx
sem mudar o visual do Office3D. Junte geometria estática para ficar em até 120 draw calls com 24 estúdios.

Teste fitSignText. Gere screenshots com 3 e 12 canais (fixtures) e me mostre. Mostre o gate G-HQ3, atualize
state.md e faça o commit "feat(hq): estúdios, letreiros e recepção (HQ-03)".
```

## HQ-04: Bonecos em multidão

```
Execute docs/studio-hq/subplans/HQ-04-crowd-figures.md (T01 a T05), seguindo design-spec.md §6.

Extraia as proporções do AgentFigure para office3d/figureProportions.ts (sem mudar o Office3D) e crie
CrowdFigures com 4 InstancedMesh (pernas, camisa, cabeça, cabelo), cores de AGENT_LOOK por instância,
UM ÚNICO useFrame para todas as poses (respiração, digitação, em pé na mesa de pauta para aprovação,
cabeça baixa em falha, pulo no done, cadeira vazia em disabled), fase diferente por boneco, caminhada curta
entre mesa e mesa de pauta, e nada de animação com prefers-reduced-motion. Só 1 balão DOM agregado por estúdio.

Implemente o LOD: estúdio em foco esconde as instâncias dele e mostra os 8 AgentFigure completos com
balões individuais. Adicione o PerfProbe (?perf=1, só em dev) e registre FPS e draw calls com 12 e 24 canais
em state.md. Mostre o gate G-HQ4, confirme que o Office3D não mudou e faça o commit
"feat(hq): agentes em multidão com LOD (HQ-04)".
```

## HQ-05: Câmera e navegação

```
Execute docs/studio-hq/subplans/HQ-05-camera-navigation.md (T01 a T05).

HQScene com dynamic import ssr:false e as mesmas opções do OfficeScene; CameraRig isométrico com pan limitado
ao prédio, zoom 0,6× a 2,5×, fitBuilding no resize, flyTo de 600 ms easeInOutCubic (instantâneo com movimento
reduzido) e flyBack. useHQNavigation com overview → focus → enter, Esc/Voltar voltando um passo.

URL: ?view=sede, ?view=sede&focus=<id> (router.replace), ?channel=<id> (router.push, escritório atual).
Recarregar restaura o estado. No StudioWorkspace, seletor "Sede | Estúdio do canal"; no menu lateral,
renomeie "Estudio 2.5D" para "Sede & Estúdios" abrindo ?view=sede; no Office3D, botão "← Sede".

Teste useHQNavigation e fitBuilding. Mostre o gate G-HQ5 (incluindo o teste manual de ida e volta com o botão
Voltar do navegador), atualize state.md e faça o commit "feat(hq): câmera, foco e navegação (HQ-05)".
```

## HQ-06: HUD, lista e mobile

```
Execute docs/studio-hq/subplans/HQ-06-hud-accessibility.md (T01 a T05), seguindo design-spec.md §8 e §9.

HQ.tsx com header (título, resumo, chip de realtime), filtros que só esmaecem, busca que realça e voa até
o estúdio, paginação por ala, cartão de hover (sem cobrir o letreiro), painel de foco de 360 px com os 8
agentes e os botões "Entrar no estúdio" e "Preparar estúdio". StudioCardList como lista acessível no desktop
e como tela principal abaixo de 768 px (sem montar WebGL). Estados: carregando (skeleton), erro com
"Tentar de novo", workspace sem canais (botão para "Canais & Perfil") e sem WebGL.

Estilo igual ao resto do app (reaproveite variáveis de office3d.module.css). Verifique 375, 768, 1280 e 1920 px
e me mostre screenshots. Mostre o gate G-HQ6, atualize state.md e faça o commit
"feat(hq): HUD, lista acessível e mobile (HQ-06)".
```

## HQ-07: Gate final

```
Execute docs/studio-hq/subplans/HQ-07-quality-gate.md (T01 a T05).

Faça uma revisão de direção de arte rigorosa contra design-spec.md (incluindo §10 "O que evitar") e
corrija o que estiver fora. Salve os screenshots listados em docs/studio-hq/reference/screens/, meça
desempenho com ?perf=1 (12 e 24 canais, primeiro quadro, memória após 5 min) e rode a regressão completa
(typecheck, test:studio, pytest, fluxo manual do escritório atual, realtime refletindo na Sede em até 2 s).

Atualize docs/studio-ui/README.md com o link para docs/studio-hq/, complete state.md com números e desvios,
faça o commit "feat(hq): gate final da Sede (HQ-07)" e abra o PR de feat/sede-canais para main com
resumo, números de desempenho e screenshots.
```

---

## Extra: prompts para gerar mais referências visuais (Midjourney, Ideogram, GPT-image)

Use se quiser mais imagens de referência antes ou durante o HQ-03. Troque os nomes entre aspas pelos seus canais.

**Sede inteira**
```
High-end isometric 3D architectural miniature of a video-production headquarters floor at night,
orthographic 45° camera, matte clay and walnut materials, central dark corridor with small studios on
both sides, warm off-white walls, each studio has a slim backlit lightbox sign above its door reading
"O Outro Lado", "<Canal 2>", "<Canal 3>" in clean dark sans-serif on a light face with a thin colored
stripe, a small round status lamp beside each sign (green, amber, red), tiny stylized people at desks
with glowing monitors, reception lobby with a wall screen, warm light spilling from doors onto the
corridor, soft ambient occlusion, premium product render, no gradients, no bloom, dark slate background.
```

**Close no letreiro**
```
Close-up isometric product render of a slim backlit lightbox sign mounted above a wooden studio door on a
warm off-white wall, circular avatar disc on the left, the text "O Outro Lado" in clean semibold dark
sans-serif, thin teal vertical stripe on the left edge, a small amber glowing status lamp to the right,
a tiny amber "EM PRODUÇÃO" plate above, matte materials, soft warm light, dark corridor floor, miniature
architectural model style, crisp, minimal.
```

**Interior de um estúdio**
```
Isometric cutaway miniature of one small video-production studio room, two rows of four compact walnut
desks with monitors (some glowing amber), eight tiny stylized low-poly people with rounded heads in
different muted shirt colors, three of them standing around a small round meeting table at the back,
one potted plant in the back-left corner, a teal rug under the desks, warm interior light, matte clay
materials, soft shadows, dark slate base, premium architectural maquette render.
```
