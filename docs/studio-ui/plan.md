# Plano — DarkForge Studio UI

## 1. Objetivo

Entregar a tela **Estúdio de Conteúdo**: uma maquete 2.5D do canal com salas clicáveis, agentes que se movem conforme o **estado real** do banco, e painéis de métricas, oportunidade e atividade. Por trás dela, a estrutura em que **cada agente de cada canal** executa como job e grava o resultado validado no banco.

## 2. Fora do escopo

- Publicação automática no YouTube (o agente de publicação só monta o plano).
- Animação "de enfeite" desconectada do estado (pessoinha andando sem run real).
- Números fixos ou de demonstração em produção.
- Uma segunda fila, um segundo banco ou um segundo mecanismo de recovery.
- 3D em tempo real (WebGL) no MVP. Fica como evolução opcional depois do gate.

## 3. Decisões de arquitetura da interface

| Decisão | Escolha | Motivo |
|---|---|---|
| Renderização da cena | **2.5D em camadas**: imagem de fundo renderizada ("clean plate" sem texto, pessoas nem painéis) + overlay SVG com polígonos das salas + sprites de agentes em DOM | Fica fiel à referência, é leve, acessível e testável; não exige 3D real |
| Coordenadas | Normalizadas (0–1) num `studio-layout.ts` versionado | Cena escala em qualquer resolução |
| Salas | `<button>` acessível sobre cada polígono, com foco visível e rótulo | Teclado e leitor de tela |
| Agentes | Sprite por agente, posicionado em âncoras da sala conforme o status (§4 de database.md) | Movimento = mudança de estado real |
| Painéis | Componentes React reais em vidro fosco sobre a cena (desktop) | Dados reais, estados `unknown`/stale |
| Mobile | Cena vira lista de salas + feed (sem maquete) | Legibilidade |
| Atualização | Snapshot inicial (server) + eventos com cursor e replay; Realtime só como transporte | Recupera após reconexão |
| Movimento | Respeita `prefers-reduced-motion` (sem deslocamento, só troca de estado) | Acessibilidade |

## 4. Ordem e dependências

```text
UI-00 Descoberta ─▶ UI-01 Banco ─▶ UI-02 Runtime dos agentes ─▶ UI-03 API de estado
                                                                     │
                       UI-04 Cena (pode começar após UI-00 com dados vazios) ──┤
                                                                     ▼
                                        UI-05 Painéis ─▶ UI-06 Interações ─▶ UI-07 Gate
```

Dependências do pacote principal:

| Precisa de | Para |
|---|---|
| SP-01 (workspace, auth, RLS, `is_workspace_member`) | UI-01 |
| SP-02 (Job Manager, leases, eventos, recovery) | UI-02 |
| SP-03 (analytics) | agente `dados` e painel do canal |
| SP-04/SP-06 (pesquisa, RAG) | agentes `pesquisa`, `estrategia`, `roteiro` |
| SP-07 (oportunidades, briefs) | aprovação e handoffs |
| SP-08 (produção DarkForge) | agente `edicao` |

Se algum SP ainda não existir, o agente correspondente fica `enabled=false` e a sala mostra "módulo indisponível". A tela **não** finge funcionamento.

## 5. Ciclo por tarefa (obrigatório)

1. Ler a tarefa `UI-xx-Tyy` e os requisitos citados.
2. Inspecionar o código real envolvido.
3. Escrever o teste ou critério verificável primeiro.
4. Implementar a menor mudança completa.
5. Rodar os checks (lint, typecheck, testes, RLS quando houver schema).
6. Atualizar `state.md`: o que mudou, evidência, próximo passo.

## 6. Gates

| Gate | Condição |
|---|---|
| G-UI0 | Mapa do código entregue; decisão de encaixe registrada (ADR) |
| G-UI1 | Migrations aplicam do zero; testes de RLS com 2 workspaces passam |
| G-UI2 | Um agente fake determinístico executa via fila real, grava output validado e handoff; crash no meio não gera "concluído" |
| G-UI3 | Snapshot + replay por cursor reconstrói o estado após desconectar |
| G-UI4 | Cena renderiza com 0 agentes, 8 agentes e todos os estados; navegável por teclado |
| G-UI5 | Painéis mostram `unknown`, stale, erro e vazio corretamente; nenhum número fixo |
| G-UI6 | Aprovar/rejeitar gera `approvals` versionado e libera ou bloqueia o handoff |
| G-UI7 | E2E do fluxo completo com agentes fake; a11y e performance dentro do orçamento |

## 7. Definição de pronto

- Cada pessoinha na tela corresponde a um `channel_agent` real, e sua posição corresponde ao status do run mais recente.
- Cada número em painel tem fonte, período e `fetched_at`, ou aparece como indisponível.
- Cada item do feed vem de `agent_events`.
- Trocar de canal troca a equipe inteira, sem vazar dados.
- Funciona por teclado, com leitor de tela e com movimento reduzido.
- Sem regressão nos gates do pacote principal.

## 8. Subplanos

- [UI-00 Descoberta e adaptação](subplans/UI-00-discovery.md)
- [UI-01 Banco dos agentes](subplans/UI-01-database.md)
- [UI-02 Runtime e escrita dos agentes](subplans/UI-02-agent-runtime.md)
- [UI-03 API de estado do studio](subplans/UI-03-studio-state-api.md)
- [UI-04 Cena do studio](subplans/UI-04-scene.md)
- [UI-05 Painéis](subplans/UI-05-panels.md)
- [UI-06 Interações e aprovação](subplans/UI-06-interactions.md)
- [UI-07 Qualidade e gate final](subplans/UI-07-quality-gate.md)
