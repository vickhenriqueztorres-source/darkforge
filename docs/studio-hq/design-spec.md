# Direção de arte: Sede DarkForge

## 1. Conceito: "maquete de arquitetura à noite"

A Sede é uma **maquete física de um prédio de produtoras**, fotografada à noite: materiais foscos
como argila e madeira, luz quente saindo das portas para o corredor escuro, e **letreiros
iluminados** com o nome de cada canal. Nada de neon exagerado, gradiente ou brilho de videogame.
A referência é um modelo de arquiteto, não um jogo.

**Assinatura visual (o que a pessoa lembra):** a fileira de letreiros acesos no corredor, cada um
com o avatar e o nome do canal, e a lâmpada de status ao lado. Todo o resto fica calmo para os
letreiros e os bonecos se destacarem.

Referência de clima: `reference/sede-conceito.png` (os nomes nos letreiros da imagem são de
exemplo; na tela eles vêm de `channel.display_name`).

## 2. Cores

Reaproveitar a `PALETTE` de `office3d/layout3d.ts` para manter o mesmo mundo. Tokens da Sede:

| Token | Valor | Uso |
| --- | --- | --- |
| `base` | `#11161c` | placa da maquete e fundo do palco |
| `corridor` | `#1b2129` | piso do corredor (fosco, leve reflexo: `roughness 0.55`) |
| `wall` | `#e7e0d3` | paredes de todos os estúdios (iguais em todos) |
| `wallCap` | `#7a5236` | acabamento do topo das paredes |
| `wood` / `woodDark` | `#8a5f3f` / `#5b3d28` | mesas, portas, recepção |
| `accent` | `#f5a623` | âmbar DarkForge: "trabalhando", seleção, "EM PRODUÇÃO" |
| `ok` / `warn` / `err` | `#3fae6a` / `#f5a623` / `#e0503f` | status (iguais ao Office3D) |

**Cor do canal** (`hqColors.ts`): uma de 8 cores foscas, escolhida por `hash(channel.id) % 8`.
Ela aparece **só** em 3 lugares: faixa lateral do letreiro, batente da porta e um tapete no piso do estúdio.
Nunca em paredes inteiras nem no texto.

```
teal #3f8f8a · rust #b0563a · olive #7d8f4a · slate #4f6f9a
ochre #c2913a · plum #8a5577 · moss #5a7a5a · clay #a8735a
```

Se dois canais vizinhos caírem na mesma cor, o layout pega a próxima cor livre (determinístico).

## 3. Tipografia

- Uma família só: a fonte sans que o app já usa no `layout.tsx`. Para o 3D, colocar o `.woff`
  dessa mesma família em `apps/web/public/fonts/` e passar para o `drei <Text font=...>`.
- Letreiro: peso 600, caixa normal (não tudo maiúsculo), `letterSpacing 0.01`.
- "EM PRODUÇÃO": peso 700, caixa alta, `letterSpacing 0.08`.
- HUD e lista DOM: mesma família, mínimo 14 px, `line-height 1.5`.

## 4. O prédio

- **Planta:** corredor central com estúdios dos dois lados (como na referência). Até 6 estúdios por lado,
  ou seja, até 12 por **ala**. Com mais de 12 canais, criar uma segunda ala paralela, ligada por um hall.
  Máximo de 24 canais (2 alas). Acima disso, paginação por ala no HUD.
- **Recepção** na entrada do corredor: balcão de madeira, parede com o logo "DarkForge" em relevo
  e um **telão** com 3 números: trabalhando, aguardando você, com problema (os mesmos totais do HUD).
- **Paredes:** externas com 2,4 de altura e meio-corte (estilo maquete) para ver o interior;
  divisórias entre estúdios com 0,95, como no Office3D. A parede do lado do corredor é a que leva o letreiro,
  e fica cortada na altura de 1,6 para não esconder os bonecos.
- **Placa da maquete:** chanfro de 0,15, borda um tom mais claro que a base. Leve sombra de contato
  no chão (`ContactShadows` do drei, opacidade 0,35).

## 5. O estúdio (um por canal)

Medidas de referência (unidades do mundo do Office3D, mesma escala dos bonecos):
módulo de **8,4 × 7**, porta de **1,3** centralizada na parede do corredor.

Dentro:
- **8 mesas compactas** em 2 fileiras de 4, cada uma com monitor. O monitor segue o padrão do Office3D:
  apagado (`screenOff`), em espera (`screenIdle`), trabalhando (`screenWork`, âmbar).
- **Mesa de pauta** pequena e redonda no fundo, onde os bonecos se reúnem quando há aprovação pendente.
- **1 vaso de planta** no canto, sempre no mesmo canto em todos os estúdios (ordem visual).
- **Tapete** na cor do canal sob as mesas.

Fora (na parede do corredor):
- **Letreiro** (`ChannelSign`): caixa de luz de 3,2 × 0,6 × 0,08, centrada acima da porta.
  À esquerda, disco com o avatar do canal (ou monograma); à direita, o nome.
  Faixa vertical de 0,08 na cor do canal na borda esquerda.
  Material da face: `meshStandardMaterial` claro com `emissive` suave (`emissiveIntensity 0.35`) para parecer aceso.
- **Lâmpada de status** (esfera de 0,12) à direita do letreiro:
  - verde fixo: tudo ok, sem trabalho;
  - âmbar pulsando devagar (1,6 s): alguém trabalhando;
  - laranja com pulso duplo: **aguardando você** (prioridade visual mais alta);
  - vermelho fixo: falha, bloqueio ou sem sinal.
  Prioridade quando há mais de um estado: vermelho > aguardando você > trabalhando > ok.
- **"EM PRODUÇÃO"**: placa pequena âmbar acesa acima do letreiro quando `active_item` existe.
- **Luz da porta**: um `pointLight` fraco e quente dentro de cada estúdio ativo, que "vaza" para o corredor.
  Para não pesar, no máximo 12 luzes pontuais acesas; acima disso, usar um plano emissivo no chão em frente à porta.

### Estados do estúdio

| Estado | Visual |
| --- | --- |
| Normal | luzes acesas, bonecos nas mesas |
| Trabalhando | monitores âmbar, bonecos digitando, lâmpada âmbar pulsando |
| Aguardando você | bonecos em pé na mesa de pauta, balão "!" laranja acima do grupo, lâmpada laranja |
| Problema | lâmpada vermelha, monitor do agente com falha vermelho |
| Sem agentes (`provisioned = false`) | estúdio "em obras": luz apagada, mesas cobertas com lona cinza, cavalete na porta; letreiro aceso normalmente com o nome; botão "Preparar estúdio" no cartão |
| Canal desconectado (`status` diferente de ativo) | estúdio inteiro com 40% de saturação, letreiro apagado (sem emissive), texto "Desconectado" no cartão |
| Esmaecido por filtro | `opacity 0.25` nas paredes e bonecos, letreiro continua legível a 60% |

## 6. Os bonecos

- Mesmo personagem do `AgentFigure` (cabeça, cabelo, camisa, pernas) e mesmas cores de `AGENT_LOOK`,
  para o usuário reconhecer o "Roteirista" em qualquer estúdio.
- Na Sede: versão simplificada instanciada (`CrowdFigures`): 4 partes, sem dedos nem detalhes.
- Animações (todas em 1 `useFrame`, com fase diferente por boneco para não ficarem sincronizados):
  - `idle`: sentado, respiração (escala Y ±1,5%, 3 s);
  - `working`: digitando (braços/ombros ±0,04, 0,35 s) e cabeça leve para o monitor;
  - `queued`: sentado, olhando para a porta;
  - `waiting_approval`/`needs_review`/`waiting_input`: em pé na mesa de pauta;
  - `failed`/`blocked`/`no_signal`: sentado, cabeça baixa, monitor vermelho;
  - `done`: pequeno pulo de 0,15 uma vez e volta para `idle`;
  - `disabled`: cadeira vazia (boneco oculto).
- Com `prefers-reduced-motion`: sem animação contínua, só a pose final de cada status.

## 7. Câmera e luz

- Câmera ortográfica isométrica igual à do Office3D (`ISO_AZIMUTH = π/4`), mesma faixa de giro (±0,55 rad).
- Enquadramento automático: zoom calculado pelo tamanho do prédio e do palco, com 6% de margem.
- Pan liberado na Sede (limitado à caixa do prédio); zoom de 0,6× a 2,5× do enquadramento.
- Voo até um estúdio: 600 ms, `easeInOutCubic`; com movimento reduzido, corte instantâneo.
- Luz: `hemisphereLight` fria e fraca (noite) + 1 `directionalLight` quente com sombra + as luzes das portas.
  O corredor fica mais escuro que o interior dos estúdios: é isso que faz os letreiros "saltarem".

## 8. HUD (DOM por cima do canvas)

- **Topo:** título "Sede DarkForge", subtítulo com "N canais · X trabalhando · Y aguardando você · Z com problema".
- **Filtros** em chips: Todos · Trabalhando · Aguardando você · Com problema · Sem agentes.
- **Busca** por nome do canal (realça e centraliza o estúdio).
- **Cartão de hover** perto do cursor: avatar, nome, handle, contadores e "Produzindo: <título>".
- **Painel de foco** (lado direito, 360 px): nome, nicho, os 8 agentes com status, item ativo e
  os botões "Entrar no estúdio" e "Preparar estúdio" (quando aplicável).
- Visual do HUD igual ao resto do app (fundo escuro, bordas finas, chips arredondados, como na barra
  "Supabase: Conectado / Realtime ativo" atual).

## 9. Acessibilidade

- A cena 3D é decorativa para leitores de tela: `role="group"` com `aria-label` explicando que a
  lista "Estúdios dos canais" tem as mesmas ações.
- Lista DOM sempre presente (visualmente na lateral no desktop, como lista principal no mobile):
  um botão por canal com nome, estado em texto e contadores.
- Teclado: Tab percorre os estúdios na ordem do layout; Enter foca; Enter de novo entra; Esc volta.
- Status nunca só por cor: a lâmpada sempre tem texto equivalente no cartão e na lista.
- Contraste mínimo 4,5:1 no HUD e nos letreiros (texto escuro `#11161c` sobre face clara).

## 10. O que evitar

- Gradientes, brilho/bloom, partículas, neon roxo.
- Cada estúdio com uma cor de parede diferente (vira bagunça; a cor do canal é só detalhe).
- Reordenar os estúdios em tempo real.
- Bonecos inventados quando não há dados.
- Textos pequenos no 3D que só dão para ler com zoom: o que é importante também está no DOM.
