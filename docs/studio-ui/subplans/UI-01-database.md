# UI-01 — Banco dos agentes

**Objetivo:** criar as tabelas, as policies e as views dos agentes por canal, adaptadas ao schema existente.  
**Depende de:** UI-00, SP-01.  
**Referências:** `database.md` §3–§8, `schema-reference.sql`.  
**Gate:** G-UI1.

## Tarefas

### UI-01-T01 — Catálogos
Criar `studio_rooms` e `agent_definitions` com seed idempotente.  
**Teste:** rodar a migration duas vezes não duplica nada.

### UI-01-T02 — Equipe por canal
Criar `channel_agents` e um trigger ou serviço que, ao criar um canal, crie os 8 agentes (desativando os que dependem de módulos indisponíveis). Backfill para os canais existentes.  
**Teste:** canal novo tem 8 linhas; `unique(channel_id, agent_key)` é respeitado.

### UI-01-T03 — Content items
Criar `content_items` com os estados de `database.md` §3.4 e as FKs para oportunidade e brief (se existirem).  
**Teste:** transição inválida de estágio é rejeitada pelo serviço de domínio.

### UI-01-T04 — Runs, eventos e outputs
Criar `agent_runs` (com FK para `jobs`), `agent_events`, `agent_outputs`, `agent_output_sources`, `agent_handoffs` e `approvals`, com índices em todas as FKs.  
**Teste:** `idempotency_key` duplicada falha; `seq` duplicado por run falha.

### UI-01-T05 — RLS
Habilitar RLS em todas as tabelas. O navegador só lê; runs, eventos, outputs e handoffs são escritos apenas pelo backend. Aprovação só com `decided_by = auth.uid()`.  
**Teste:** com dois workspaces, o usuário A não lê nem escreve nada do B; o navegador não consegue inserir em `agent_outputs`.

### UI-01-T06 — Views de leitura
Criar `v_studio_agent_state`, `v_studio_room_state` e `v_content_pipeline` com `security_invoker = true`.  
**Teste:** as views respeitam RLS; heartbeat antigo aparece como `no_signal`.

### UI-01-T07 — Tipos gerados
Gerar os tipos TypeScript do banco e os repositórios de leitura.  
**Teste:** o typecheck passa.

## Gate G-UI1
- [ ] Migrations aplicam do zero e são reaplicáveis
- [ ] Testes de RLS com dois workspaces verdes
- [ ] Views retornam o estado correto para todos os status
- [ ] Tipos gerados e typecheck verde
