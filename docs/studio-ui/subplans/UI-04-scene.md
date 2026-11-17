# UI-04 — Cena do studio

**Objetivo:** renderizar a maquete 2.5D com salas interativas e agentes posicionados pelo estado.  
**Depende de:** UI-00 (pode usar estado vazio); integra com UI-03.  
**Referência:** `reference/studio-reference.png`, `plan.md` §3.  
**Gate:** G-UI4.

## Tarefas

### UI-04-T01 — Layout normalizado
Criar `studio-layout.ts`: para cada sala, `polygon` (pontos 0–1), `labelAnchor`, `door`, `desks[]` e `meeting[]` (sala central). Versionar junto com o clean plate.  
**Teste:** todos os pontos ficam entre 0 e 1; cada sala tem pelo menos uma mesa por agente.

### UI-04-T02 — Palco responsivo
Componente `StudioStage`: imagem de fundo (`next/image` ou equivalente, com prioridade), SVG por cima com o mesmo `viewBox`, mantendo a proporção.  
**Teste:** em 1280, 1440 e 1920px de largura, os polígonos continuam alinhados à imagem.

### UI-04-T03 — Salas interativas
Cada sala vira um `<button>` sobre o polígono, com nome, contagem de agentes e badge de estado (trabalhando, aguardando, bloqueado). Hover e foco realçam o contorno com a cor de destaque.  
**Teste:** dá para navegar por Tab em ordem lógica; Enter abre a gaveta da sala.

### UI-04-T04 — Sprites de agentes
Componente `AgentSprite` com avatar, nome curto e indicador de status. A posição vem de `resolveAgentPosition(agent, layout)` conforme a tabela de `database.md` §4. Movimento por `transform`, de 400 a 800ms.  
**Teste:** cada status gera a posição e o ícone corretos (teste unitário da função).

### UI-04-T05 — Movimento reduzido e mobile
Com `prefers-reduced-motion`, a troca de posição é instantânea. Abaixo de 768px, a cena vira `StudioRoomList` (cards de sala + agentes).  
**Teste:** snapshot visual nos dois modos.

### UI-04-T06 — Estados vazios e de erro
Canal sem agentes, módulo indisponível (sala esmaecida com motivo), carregando (skeleton sobre a imagem) e erro de carregamento.  
**Teste:** cada estado renderiza sem quebrar o layout.

## Gate G-UI4
- [ ] Renderiza com 0 e com 8 agentes, em todos os status
- [ ] Polígonos alinhados em 3 larguras
- [ ] Navegável por teclado, com movimento reduzido e no mobile
