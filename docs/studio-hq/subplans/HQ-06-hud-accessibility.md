# HQ-06: HUD, lista acessível e mobile

**Objetivo:** tudo o que a cena mostra também precisa estar no DOM: legível, navegável por teclado e no celular.
**Depende de:** HQ-05.
**Referência:** `design-spec.md` §8 e §9.
**Gate:** G-HQ6.

## Tarefas

### HQ-06-T01: `HQ.tsx` (seção)
- Header: título "Sede DarkForge", resumo "N canais · X trabalhando · Y aguardando você · Z com problema",
  indicador de tempo real (mesmo chip "Realtime ativo" do app).
- Chips de filtro (`HQFilter`) com contagem; filtro esmaece estúdios (`dimmed`), não move.
- Busca por nome (debounce 150 ms): realça o estúdio encontrado e faz `flyTo`.
- Paginação por ala quando `overflow > 0`.
- Estilos em `hq.module.css` seguindo `office3d.module.css` (mesmas variáveis, mesmos raios e bordas).

### HQ-06-T02: Cartão de hover
Perto do cursor (ou ancorado no letreiro via `OverlaySync`): avatar, nome completo, handle,
contadores com texto, "Produzindo: <título>" e "Última atividade há X min". Nunca cobre o próprio letreiro.

### HQ-06-T03: Painel de foco
Lateral direita de 360 px no desktop: nome, nicho, item ativo, os 8 agentes com nome (`AGENT_LOOK`) e status em texto,
botões "Entrar no estúdio" e "Preparar estúdio" (quando `provisioned = false`, chama `prepareStudio`, mostra progresso
e erro amigável). Foco do teclado vai para o painel ao abrir e volta para o estúdio ao fechar.

### HQ-06-T04: `StudioCardList.tsx`
- Lista "Estúdios dos canais": um `<button>` por canal com nome, estado em texto, contadores e lâmpada com rótulo.
- Desktop: coluna à esquerda do palco, recolhível. Tab percorre na mesma ordem do layout; Enter = focar; Enter de novo = entrar.
- **Abaixo de 768 px**: a cena 3D não monta; a lista vira a tela principal em cartões (avatar, nome, lâmpada, contadores, "Entrar").

### HQ-06-T05: Estados da tela
- Carregando: skeleton do prédio (placa + retângulos) e lista com skeleton.
- Erro: mensagem com o código do erro do `ApiClientError` e botão "Tentar de novo".
- Workspace sem canais: estado vazio com ilustração da recepção vazia e botão "Conectar canal" (leva para "Canais & Perfil").
- Sem WebGL: lista em cartões (igual mobile) com aviso discreto.

## Testes
- Componente: lista renderiza todos os canais das fixtures com textos de status corretos.
- Teclado: Tab/Enter/Esc percorrem foco → entrar → voltar.
- Leitor de tela: cada botão tem `aria-label` vindo de `studioSummaryText`.

## Gate G-HQ6
- [ ] Todas as ações da cena disponíveis só com teclado
- [ ] Status nunca só por cor (texto sempre presente)
- [ ] 375 px, 768 px, 1280 px e 1920 px sem sobreposição nem texto cortado
- [ ] Estados de carregando, erro, vazio e sem WebGL implementados
