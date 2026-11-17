# UI-02 — Runtime e escrita dos agentes

**Objetivo:** fazer cada agente de cada canal rodar como job, validar a saída e gravá-la no banco de forma atômica, criando os handoffs.  
**Depende de:** UI-01, SP-02.  
**Referências:** `database.md` §5–§6, `agent-contracts.md`.  
**Gate:** G-UI2.

## Tarefas

### UI-02-T01 — Registro de agentes no código
Criar o registro `agentKey → { contractVersion, inputLoader, promptBuilder, outputSchema, validators, nextAgents }`.  
**Teste:** cada `agent_definitions.key` tem entrada no registro e vice-versa.

### UI-02-T02 — Schemas executáveis
Transformar os payloads de `agent-contracts.md` §2 em schemas executáveis versionados, no padrão do repositório.  
**Teste:** exemplos válidos passam; métrica ausente como 0, `requires_human_publish=false` e campos extras rejeitados.

### UI-02-T03 — Enfileirar um agente
Criar o serviço `enqueueAgentRun({ workspaceId, channelId, agentKey, contentItemId?, reason })`: cria o job na fila única, cria o `agent_run` (`queued`) com `idempotency_key` e grava o evento `run_queued`.  
**Teste:** chamar duas vezes com a mesma intenção cria um único run.

### UI-02-T04 — Executor do worker
Handler do job: claim com lease → `working` + `run_started` → carrega o contexto autorizado → monta o prompt (template §4) → chama o modelo pela política do canal → valida → 1 tentativa de reparo → persiste. Heartbeat periódico com `stage_label` e `progress` real ou `null`.  
**Teste:** com um modelo fake determinístico, o run termina `done` com output e fontes.

### UI-02-T05 — Persistência atômica com fencing
Numa única transação: output, fontes, eventos, handoffs e status do run e do job, verificando o fencing token.  
**Teste:** worker com lease expirado não consegue gravar; falha no commit não deixa nada como `done`.

### UI-02-T06 — Validações de negócio
Aplicar as regras de `agent-contracts.md` §3 (escopo, fontes existentes, similaridade, temas proibidos, publicação humana).  
**Teste:** cada regra tem um caso que leva a `needs_review` ou `failed`.

### UI-02-T07 — Handoffs e orquestração
Ao validar (e aprovar, quando exigido), criar `agent_handoffs` para os próximos agentes e enfileirar os runs deles. Agentes que dependem de mais de uma entrada (`estrategia` ← `dados` + `pesquisa`) só iniciam quando todas estiverem prontas.  
**Teste:** o fluxo de `database.md` §5 roda ponta a ponta com agentes fake.

### UI-02-T08 — Recovery
Integrar ao recovery do SP-02: run `working` com lease vencido volta para `queued` (com `attempt` +1) ou vai para `failed` após o limite.  
**Teste:** matar o worker no meio não deixa run "trabalhando" para sempre.

## Gate G-UI2
- [ ] Agente fake executa via fila real e grava output validado com fontes
- [ ] Crash no meio não gera "concluído"
- [ ] Idempotência e fencing testados
- [ ] Handoffs disparam os próximos agentes corretamente
