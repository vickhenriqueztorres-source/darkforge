# DarkForge Studio UI — interface "estúdio com agentes"

Pacote para a IDE implementar a interface do estúdio da [imagem de referência](reference/studio-reference.png) e o banco que cada agente de cada canal usa para registrar seu trabalho.

![Referência do estúdio](reference/studio-reference.png)

> Os números da imagem (3,48 mi, CTR 8,4%, score 82) são ilustrativos. Na implementação, todo número vem do banco ou aparece como `unknown`.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| [master-prompt.md](master-prompt.md) | **Superprompt** para colar na IDE e executar tudo |
| [plan.md](plan.md) | Plano, ordem, dependências, gates e definição de pronto |
| [database.md](database.md) | Modelo de dados dos agentes, estados, RLS e regras de escrita |
| [schema-reference.sql](schema-reference.sql) | SQL de referência (adaptar ao schema existente antes de aplicar) |
| [agent-contracts.md](agent-contracts.md) | Responsabilidade, entradas, saídas JSON e prompt-base de cada agente por canal |
| [state.md](state.md) | Estado vivo da execução para retomar sem perder contexto |
| [adr/ADR-UI-001-encaixe.md](adr/ADR-UI-001-encaixe.md) | ADR de encaixe do Studio UI no repositório real |
| [how-to-add-agent.md](how-to-add-agent.md) | Guia prático para adicionar um novo agente por canal |
| [subplans/](subplans/) | UI-00 a UI-07, com tarefas `UI-xx-Tyy` e gates |

## Subplanos

| ID | Arquivo | Resultado |
|---|---|---|
| UI-00 | [Descoberta e adaptação](subplans/UI-00-discovery.md) | Mapa do código real e decisão de encaixe |
| UI-01 | [Banco dos agentes](subplans/UI-01-database.md) | Tabelas, RLS, views e migrations |
| UI-02 | [Runtime e escrita dos agentes](subplans/UI-02-agent-runtime.md) | Equipe por canal, runs, outputs validados e handoffs |
| UI-03 | [API de estado do studio](subplans/UI-03-studio-state-api.md) | Snapshot + eventos com replay |
| UI-04 | [Cena do studio](subplans/UI-04-scene.md) | Maquete 2.5D com salas clicáveis e agentes animados |
| UI-05 | [Painéis](subplans/UI-05-panels.md) | Canal, oportunidade, atividade e gavetas das salas |
| UI-06 | [Interações e aprovação](subplans/UI-06-interactions.md) | Iniciar, pausar, aprovar e rejeitar com histórico |
| UI-07 | [Qualidade e gate final](subplans/UI-07-quality-gate.md) | Testes, acessibilidade, performance e aceite |

## Relação com o pacote principal

Este pacote é uma camada sobre o plano de execução (`docs/execution`). Ele **não cria** uma segunda fila, um segundo banco nem um segundo mecanismo de recovery: os agentes rodam como jobs do Job Manager único (SP-02), e as saídas alimentam oportunidades, briefs e produção (SP-07/SP-08).

## Como usar

1. Coloque `docs/studio-ui/` no repositório, junto de `docs/prd.md`, `docs/architecture.md` e `docs/execution/`.
2. Copie todo o [master-prompt.md](master-prompt.md) e cole no agente da IDE.
3. Credenciais só pelo gerenciador de ambiente da IDE.
4. A IDE atualiza `state.md` a cada tarefa.
