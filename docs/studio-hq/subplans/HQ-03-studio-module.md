# HQ-03: Módulo de estúdio, letreiro e recepção

**Objetivo:** construir a maquete: prédio, estúdios com letreiro do lado de fora, recepção com telão.
**Depende de:** HQ-02.
**Referência:** `design-spec.md` §4, §5 e `reference/sede-conceito.png`.
**Gate:** G-HQ3.

## Tarefas

### HQ-03-T01: Prédio e corredor (`HQBuilding.tsx`)
Placa da maquete com chanfro, piso do corredor, paredes externas meio-cortadas, divisórias entre estúdios
(altura `PARTITION_HEIGHT` do Office3D), parede do corredor com 1,6 de altura e vãos das portas.
Reaproveitar os helpers de parede/piso de `office3d/OfficeRooms.tsx` (extrair para `office3d/primitives.tsx`
se precisar, sem mudar o visual do Office3D). Juntar paredes estáticas com `mergeGeometries` ou `<Instances>`
para reduzir draw calls.

### HQ-03-T02: `StudioModule.tsx`
Props: `slot`, `channel`, `color`, `lamp`, `dimmed`, `focused`, `hovered`, `onSelect`, `onHover`.
- Piso do estúdio, tapete na cor do canal, batente da porta na cor do canal.
- 8 mesas com monitor (estado do monitor por agente, mesmas cores do Office3D), cadeiras, mesa de pauta, planta.
- Estado "em obras" (`provisioned = false`): mesas cobertas com lona cinza, cavalete na porta, luz interna apagada.
- Canal desconectado: materiais com saturação reduzida (trocar cor por versão dessaturada calculada uma vez).
- `dimmed` (filtro): opacidade 0,25 nas paredes e móveis.
- Área de clique: uma caixa invisível do tamanho do estúdio com `onPointerOver/Out/Click`;
  cursor `pointer`; `e.stopPropagation()`.
- Hover/foco: contorno do batente e do topo das paredes na cor `accent`.

### HQ-03-T03: `ChannelSign.tsx` (assinatura visual)
- Caixa de luz 3,2 × 0,6 × 0,08 com face clara e `emissive` leve; faixa de 0,08 na cor do canal à esquerda.
- Disco do avatar (raio 0,22): textura de `avatar_url` via `useTexture` dentro de `Suspense` com
  `crossOrigin="anonymous"`; em erro ou `null`, monograma (2 iniciais) sobre a cor do canal.
- Nome com `drei <Text>`: fonte local de `apps/web/public/fonts/`, `anchorX="left"`, `maxWidth` = espaço livre,
  `fontSize` inicial 0,26 reduzindo até 0,17 para caber em 1 linha; abaixo disso, cortar com "…".
  Texto escuro `#11161c` sobre a face clara (contraste ≥ 4,5:1).
- Lâmpada de status ao lado (esfera 0,12) com material `emissive` na cor do `lamp`;
  pulso de `emissiveIntensity` conforme `design-spec.md` §5 (sem pulso com movimento reduzido).
- Placa "EM PRODUÇÃO" âmbar acima do letreiro quando `active_item` existe.
- Canal desconectado: letreiro sem `emissive`.

### HQ-03-T04: Recepção (`Lobby.tsx`)
Balcão de madeira, parede com "DarkForge" em relevo (`<Text>` com `depth` ou extrude simples), telão com 3 números
(trabalhando, aguardando você, com problema) renderizados com `<Text>`, 2 plantas, 1 boneco recepcionista estático
(cor neutra, não é agente).

### HQ-03-T05: Luz
`hemisphereLight` fria e fraca, `directionalLight` quente com sombra (mapa 2048), `pointLight` fraco dentro dos
estúdios ativos (no máximo 12; acima disso, plano emissivo no chão em frente à porta). `ContactShadows` sob a placa.

## Testes
- Unitário: função `fitSignText(name, maxWidth)` (cálculo do tamanho/corte) com nomes curtos, longos, acentuados e emoji.
- Visual (manual, registrar screenshot em `state.md`): 3 e 12 canais, um de cada estado.

## Gate G-HQ3
- [ ] Prédio com 1, 3, 12 e 24 estúdios renderizando sem sobreposição
- [ ] Letreiro mostra o nome de cada canal do lado de fora, legível no enquadramento padrão a 1440p
- [ ] Todos os estados do estúdio visíveis e distinguíveis (incluindo "em obras" e desconectado)
- [ ] ≤ 120 draw calls com 24 estúdios (sem bonecos ainda)
