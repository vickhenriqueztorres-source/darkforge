# Banco de dados dos agentes do studio

**Banco:** Supabase Postgres (fonte de verdade).  
**Regra principal:** cada canal tem sua própria equipe de agentes. Todo trabalho de agente é um registro rastreável: quem fez, para qual canal, com quais fontes, em qual versão e com qual resultado.

---

## 1. Princípios

1. **Agente não escreve SQL.** O modelo de IA devolve JSON. O worker valida esse JSON contra um schema versionado e persiste em transação, por um repositório/RPC do backend.
2. **Agente roda como job.** Cada `agent_run` aponta para um job da fila única (SP-02). Não existe fila própria do studio.
3. **Escopo obrigatório.** Toda linha tem `workspace_id` e `channel_id`. RLS por membership do workspace.
4. **Concluído = persistido e validado.** Um agente só aparece como "pronto" quando o output foi salvo e passou na validação.
5. **Append-only onde há histórico.** Eventos e outputs não são sobrescritos; nova versão substitui (`superseded`) a anterior.
6. **Aprovação humana** para oportunidade → brief, brief → produção e plano de publicação. Nenhum agente publica.
7. **Progresso desconhecido é `null`**, não 0% nem 100%.
8. **Fontes sempre ligadas.** Output sem fonte mínima não pode virar `validated` (exceto tipos explicitamente sem fonte, como status de produção).

---

## 2. Mapa entidade-relacionamento

```text
workspaces ─┬─ channels ─┬─ channel_agents (1 por agente por canal)
            │            │        │
            │            ├─ content_items (o vídeo/episódio que percorre o studio)
            │            │        │
            │            │        ├─ agent_runs ──── jobs (fila única existente)
            │            │        │      │
            │            │        │      ├─ agent_events (feed / replay)
            │            │        │      └─ agent_outputs ── agent_output_sources
            │            │        │                │
            │            │        ├─ agent_handoffs (passa output de um agente ao próximo)
            │            │        └─ approvals (decisões humanas por versão)
            │
agent_definitions (catálogo global) ── studio_rooms (catálogo de salas)
```

---

## 3. Tabelas

### 3.1 `studio_rooms` (catálogo)

As salas da maquete. O layout visual (coordenadas) fica no código; o banco guarda só a identidade.

| key | label |
|---|---|
| `sala_dados` | Sala de Dados |
| `pesquisa` | Pesquisa |
| `mesa_agentes` | Agentes de IA (sala central) |
| `gravacao` | Gravação |
| `design_thumbnail` | Design – Thumbnail |
| `estrategia_publicacao` | Estratégia e Publicação |

### 3.2 `agent_definitions` (catálogo global)

Um registro por tipo de agente, com versão do contrato.

| key | Sala | Faz |
|---|---|---|
| `dados` | sala_dados | Interpreta analytics sincronizados do canal |
| `pesquisa` | pesquisa | Pesquisa referências públicas e valida temas |
| `estrategia` | mesa_agentes | Gera e pontua oportunidades |
| `titulos` | mesa_agentes | Analisa e propõe títulos |
| `roteiro` | mesa_agentes | Escreve outline e roteiro |
| `thumbnail` | design_thumbnail | Propõe conceitos de capa |
| `edicao` | gravacao | Acompanha a produção DarkForge |
| `publicacao` | estrategia_publicacao | Monta plano de publicação para aprovação |

Campos: `key`, `display_name`, `room_key`, `description`, `output_types[]`, `requires_approval`, `contract_version`, `active`.

### 3.3 `channel_agents` (equipe de cada canal)

Um registro por agente por canal (`unique(channel_id, agent_key)`). Guarda configuração específica do canal: nome de exibição, avatar, política de modelo (local/externo com consentimento), orçamento, ativo/inativo.

### 3.4 `content_items` (o vídeo que percorre o studio)

Representa um episódio desde a ideia até a publicação manual. Liga oportunidade, brief aprovado e produção.

- `stage`: `ideia` → `pesquisa` → `estrategia` → `roteiro` → `design` → `producao` → `publicacao` → `publicado_manual` | `arquivado`
- `status`: `ativo`, `aguardando_aprovacao`, `bloqueado`, `concluido`, `arquivado`
- `scheduled_for`: data planejada (não dispara publicação)

### 3.5 `agent_runs` (cada execução de um agente)

| Campo | Significado |
|---|---|
| `job_id` | FK para o job da fila única |
| `channel_agent_id`, `agent_key` | Quem executa |
| `content_item_id` | Para qual vídeo (opcional para agentes de canal, como `dados`) |
| `status` | ver §4 |
| `stage_label` | Etapa real informada pelo worker ("buscando referências") |
| `progress` | 0–1 ou `null` quando desconhecido |
| `idempotency_key` | Impede execução duplicada da mesma intenção |
| `input_hash`, `prompt_version`, `model_id`, `provider` | Reprodutibilidade |
| `cost_estimate_cents` | Custo estimado |
| `error_code`, `error_message` | Erro já sem dados sensíveis |

### 3.6 `agent_events` (feed "Atividade dos Agentes")

Append-only, com `seq` por run (`unique(run_id, seq)`). Tipos: `run_queued`, `run_started`, `stage_changed`, `progress`, `output_saved`, `output_validated`, `needs_review`, `handoff_created`, `blocked`, `failed`, `cancelled`, `completed`. O feed da UI lê daqui e permite replay por cursor.

### 3.7 `agent_outputs` (o que o agente produziu)

| Campo | Significado |
|---|---|
| `output_type` | ex.: `opportunity`, `title_options`, `script_draft` |
| `schema_version` | versão do JSON schema validado |
| `version` | incrementa por content_item + output_type |
| `content` | JSON validado |
| `content_hash` | dedupe |
| `status` | `draft`, `validated`, `needs_review`, `approved`, `rejected`, `superseded` |
| `validation` | resultado da validação (erros, avisos, similaridade) |

### 3.8 `agent_output_sources` (proveniência)

Liga output a métricas, referências de pesquisa, chunks RAG, versão de perfil do canal ou outputs de outros agentes.

### 3.9 `agent_handoffs` (passagem de bastão)

Quando um output é validado (e aprovado, se exigido), o worker cria um handoff para o próximo agente. Estados: `pending`, `accepted`, `consumed`, `cancelled`. Isso move as pessoinhas entre as salas na UI.

### 3.10 `approvals`

Decisão humana sobre um alvo versionado (`target_kind`, `target_id`, `target_version`): `approved`, `rejected`, `changes_requested`, com motivo, autor e data. Aprovar congela a versão.

---

## 4. Estados do agente (o que a pessoinha está fazendo)

| `agent_runs.status` | Na cena | Significado |
|---|---|---|
| `idle` (sem run ativo) | parado na sua sala | nada para fazer |
| `queued` | na porta da sala | job criado, aguardando worker |
| `working` | na mesa, animado | worker com lease ativo e heartbeat recente |
| `waiting_input` | sentado, ícone de relógio | aguardando handoff ou dado |
| `needs_review` | balão amarelo | output salvo, precisa de revisão humana |
| `waiting_approval` | indo para a sala central | aguardando aprovação humana |
| `blocked` | ícone de cadeado | quota, rede, credencial ou modelo indisponível |
| `failed` | luz vermelha | falhou, com retry disponível |
| `cancelled` | volta à sala | cancelado |
| `done` | check verde | output persistido e validado |

**Heartbeat atrasado** (lease vencendo sem update) aparece como "sem sinal", nunca como "trabalhando".

---

## 5. Fluxo de handoff padrão

```text
dados ──────┐
            ├─▶ estrategia ─▶ [aprovação: oportunidade]
pesquisa ───┘                         │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
                 titulos           roteiro          thumbnail
                    └─────────────────┼─────────────────┘
                                      ▼
                          [aprovação: brief congelado]
                                      ▼
                                edicao (produção DarkForge)
                                      ▼
                                 publicacao
                                      ▼
                     [aprovação: plano] → humano publica manualmente
```

---

## 6. Como um agente "manda pro banco"

```text
1. Worker faz claim do job (lease + fencing token).
2. Carrega contexto autorizado: canal, versão do perfil, handoffs, fontes.
3. Grava agent_events: run_started.
4. Chama o modelo com o prompt-base do agente (agent-contracts.md).
5. Recebe JSON → valida com o schema da versão do contrato.
   - inválido: 1 retry de reparo; se falhar, status failed com erro.
6. Em UMA transação, verificando o fencing token:
   - insere agent_outputs (validated ou needs_review)
   - insere agent_output_sources
   - insere agent_events (output_saved, output_validated)
   - cria agent_handoffs, se aplicável
   - atualiza agent_runs.status e o job
7. Se o commit falhar, nada aparece como concluído; o job fica recuperável.
```

Nada disso roda com credencial privilegiada no navegador. O LLM nunca recebe credenciais de banco.

---

## 7. Views de leitura para a UI

- `v_studio_agent_state`: por canal e agente, o run mais recente, status, etapa, progresso e heartbeat.
- `v_studio_room_state`: por canal e sala, quantidade de agentes trabalhando, aguardando aprovação, bloqueados e com falha.
- `v_content_pipeline`: por content_item, estágio atual e último output por tipo (alimenta o painel "Atividade dos Agentes").

As views devem respeitar RLS (`security_invoker = true`).

---

## 8. Índices essenciais

- `agent_runs (channel_id, status)`, `agent_runs (content_item_id, agent_key, created_at desc)`
- `agent_events (channel_id, id)` para replay por cursor
- `agent_outputs (content_item_id, output_type, version desc)`
- `agent_handoffs (to_agent_key, status)`
- Todas as FKs indexadas.

O SQL de referência está em [schema-reference.sql](schema-reference.sql).
