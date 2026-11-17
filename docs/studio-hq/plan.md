# Plano mestre: Sede DarkForge (visão geral de todos os canais)

## 1. Objetivo

Criar uma tela **"Sede"** que mostra, numa maquete 3D isométrica, **um estúdio por canal** do
workspace. Cada estúdio:

- tem o **nome do canal num letreiro iluminado do lado de fora**, em cima da porta, virado para o corredor;
- mostra os **8 bonecos dos agentes daquele canal** trabalhando lá dentro, com a postura certa para cada status;
- indica o estado do canal sem precisar clicar: lâmpada de status, letreiro "EM PRODUÇÃO" e contadores;
- abre o escritório detalhado que já existe (`Office3D`) quando o usuário entra nele.

Critério de sucesso: em **3 segundos** olhando a Sede, o dono do workspace sabe quais canais estão
produzindo, quais estão esperando por ele e quais têm problema.

## 2. O que NÃO muda

- `components/studio/office3d/*` continua sendo o escritório de um canal. Reaproveitar, não reescrever.
- Rotas existentes de `/api/v1/studio/channels/{id}/...` continuam iguais.
- Tipos `AgentKey`, `RoomKey`, `AgentVisualStatus` e `agentBubble()` são a fonte única de status.
- Nenhum dado falso: se não há agentes, o estúdio aparece "em obras", nunca com bonecos inventados.

## 3. Decisões

| # | Decisão | Motivo |
| --- | --- | --- |
| D1 | Um endpoint agregado `GET /api/v1/studio/overview` em vez de N chamadas de snapshot | 1 request para 24 canais; sem cascata de loading |
| D2 | GET da Sede **não provisiona** agentes; estúdio vazio mostra botão "Preparar estúdio" | GET sem efeito colateral em massa; o snapshot do canal já provisiona sob demanda |
| D3 | Prédio gerado por código (`layoutHQ.ts`) a partir do número de canais | Funciona com 1 a 24 canais sem modelagem manual |
| D4 | Bonecos da Sede usam `InstancedMesh` (multidão), não o `AgentFigure` completo | 24 × 8 = 192 bonecos com poucas draw calls |
| D5 | Ao focar um estúdio, só aquele estúdio troca para `AgentFigure` completo (LOD) | Detalhe onde o olho está, custo baixo no resto |
| D6 | Letreiro com o nome é 3D (`drei <Text>`) e também existe como botão DOM acessível | O 3D é a assinatura visual; o DOM garante teclado, leitor de tela e texto nítido |
| D7 | Cor de destaque por canal vem de uma paleta curada de 8 tons, escolhida por hash do `channel.id` | Diferencia salas sem quebrar a identidade visual |
| D8 | Tempo real via `agent_events` filtrado por `workspace_id`, com refetch do overview em debounce | Reaproveita o canal Realtime que já existe |
| D9 | URL: `?view=sede` para a Sede, `?view=sede&focus=<channelId>` para o foco, `?channel=<id>` para o escritório | Link compartilhável e botão Voltar do navegador funcionando |
| D10 | Abaixo de 768px a Sede vira lista de cartões de estúdio (sem WebGL) | Legibilidade e bateria no celular |

## 4. Arquitetura

### Backend
- `migrations/0018_studio_hq_overview.sql`: view `v_studio_channel_overview` (`security_invoker = true`,
  `GRANT SELECT ... TO authenticated`) agregando `v_studio_agent_state` por canal, mais o item de conteúdo
  ativo mais recente e o último evento.
- `core/studio/service.py`: `get_overview(actor, workspace_id)` com `require_membership`.
- `adapters/supabase_db/...`: método de repositório `get_overview(workspace_id)`.
- `apps/api/routes/studio.py`: `GET /api/v1/studio/overview`.
- Avatar: vem do cache do canal público do YouTube quando existir (`adapters/youtube/public_channel.py`);
  o overview **nunca** dispara busca externa. Sem cache, `avatar_url = null` e o front usa monograma.

### Frontend
```
apps/web/src/components/studio/hq/
  HQ.tsx               // seção: header, HUD, palco, lista acessível, estados vazio/erro/loading
  HQScene.tsx          // Canvas (dynamic import, ssr:false), câmera, luz, prédio, multidão
  layoutHQ.ts          // geometria pura do prédio: alas, corredor, módulos, portas, letreiros, mesas
  StudioModule.tsx     // um estúdio: piso, paredes, porta, letreiro, lâmpada, mesas, "EM PRODUÇÃO"
  ChannelSign.tsx      // letreiro 3D com avatar + nome (auto-ajuste) + faixa de cor do canal
  CrowdFigures.tsx     // bonecos instanciados de todos os estúdios (1 useFrame)
  Lobby.tsx            // recepção, parede com logo DarkForge, telão com totais
  CameraRig.tsx        // enquadrar prédio, voar até um estúdio, voltar
  StudioCardList.tsx   // fallback mobile e lista acessível
  hq.module.css
  hqColors.ts          // paleta curada e hash do canal
apps/web/src/lib/studio/hq-types.ts   // contrato do overview
apps/web/src/lib/api.ts               // api.getStudioOverview()
```

`StudioWorkspace.tsx` ganha o seletor **Sede | Estúdio do canal** e lê/escreve a URL (D9).
O item do menu lateral "Estudio 2.5D" passa a se chamar **"Sede & Estúdios"**.

## 5. Contrato do overview (resumo; o detalhe está no HQ-00)

```ts
type StudioOverview = {
  workspace_id: string;
  snapshot_at: string;
  totals: { channels: number; working: number; awaiting_human: number; problems: number };
  channels: Array<{
    channel: { id: string; display_name: string; handle: string | null; status: string;
               avatar_url: string | null; niche: string | null };
    provisioned: boolean;                      // false = 0 agentes
    agents: Array<{ agent_key: AgentKey; room_key: RoomKey; status: AgentVisualStatus;
                    enabled: boolean; progress: number | null }>;
    counts: { working: number; awaiting_human: number; blocked: number; failed: number;
              agents: number; disabled_agents: number };
    active_item: { id: string; working_title: string; stage: string } | null;
    last_event_at: string | null;
  }>;
};
```

Ordem dos canais: a mesma de `api.listChannels` (ordem estável). Nunca reordenar por status em tempo real
(salas trocando de lugar desorientam). Filtros só esmaecem salas, não as movem.

## 6. Fluxo de interação

1. **Sede**: prédio enquadrado, câmera isométrica, arrastar move (pan), roda/pinça dá zoom com limites.
2. **Passar o mouse** num estúdio: contorno da porta acende na cor do canal, cartão flutuante com nome,
   contadores e "Produzindo: <título>".
3. **Clicar** (ou Enter na lista): câmera voa até o estúdio (600 ms), bonecos daquele estúdio viram
   `AgentFigure` completos com balões, painel lateral mostra o resumo do canal e o botão **Entrar no estúdio**.
4. **Entrar no estúdio**: abre o `Office3D` atual daquele canal (`?channel=<id>`).
5. **Voltar** (botão, `Esc` ou Voltar do navegador): retorna ao passo anterior.

## 7. Subplanos

| Id | Nome | Entrega | Gate |
| --- | --- | --- | --- |
| HQ-00 | Descoberta e contratos | tipos, contrato, fixtures, `state.md` | G-HQ0 |
| HQ-01 | Dados agregados | view SQL, serviço, rota, cliente, realtime | G-HQ1 |
| HQ-02 | Layout procedural do prédio | `layoutHQ.ts` + testes de 1 a 24 canais | G-HQ2 |
| HQ-03 | Módulo de estúdio e letreiro | `StudioModule`, `ChannelSign`, `Lobby` | G-HQ3 |
| HQ-04 | Bonecos em multidão | `CrowdFigures` instanciado + LOD | G-HQ4 |
| HQ-05 | Câmera, navegação e URL | `CameraRig`, foco, entrar/voltar, `?view=sede` | G-HQ5 |
| HQ-06 | HUD, lista acessível e mobile | header, filtros, busca, cartões, teclado | G-HQ6 |
| HQ-07 | Gate visual e de desempenho | screenshots, FPS, estados, regressão do Office3D | G-HQ7 |

## 8. Orçamento de desempenho (vale para todos os subplanos)

- 12 canais: ≥ 55 FPS a 1440p em GPU integrada; 24 canais: ≥ 45 FPS.
- ≤ 180 draw calls com 24 canais (conferir em `renderer.info.render.calls`).
- 1 `useFrame` para a multidão inteira; nada de `useFrame` por boneco na Sede.
- `frameloop="demand"` quando nenhum agente estiver `working` e não houver transição de câmera;
  `invalidate()` nos eventos. Pausar quando a seção sair da tela (como o Office3D já faz).
- Sombras: 1 luz direcional com sombra; `shadow-mapSize` 2048; móveis pequenos não projetam sombra.
- Fonte do letreiro carregada uma vez (arquivo local em `apps/web/public/fonts/`).

## 9. Riscos

| Risco | Mitigação |
| --- | --- |
| Nomes longos de canal estourando o letreiro | auto-ajuste de fonte até um mínimo; acima disso reticências + nome completo no cartão e no `aria-label` |
| Avatar externo sem CORS | `crossOrigin = "anonymous"`; se falhar, monograma (iniciais) na cor do canal |
| Muitos eventos em tempo real | debounce de 400 ms e no máximo 1 refetch por segundo |
| Regressão no escritório atual | HQ-07 roda os testes do studio e compara screenshot do Office3D antes/depois |
