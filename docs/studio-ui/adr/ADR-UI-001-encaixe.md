# ADR-UI-001 — Encaixe do DarkForge Studio UI no Repositório Existente

- **Status:** Aceito (UI-00)
- **Data:** 2026-11-17
- **Contexto:** O repositório `d:\YOUTUBE MANAGET` já possui os subplanos `SP-00` a `SP-27` implementados com FastAPI (`apps/api`), domínio hexagonal em Python (`core/`, `adapters/`, `workers/`), migrations Postgres/Supabase (`migrations/0001..0014`), e frontend Next.js 15 / React 19 (`apps/web`). O pacote `docs/studio-ui/` traz o SQL e os contratos como referência conceitual e exige adaptação ao código real.

---

## 1. Mapa do Repositório Real

| Camada | Tecnologia / Padrão Real | Caminhos Reais |
|---|---|---|
| **Frontend** | Next.js `15.3.0` (App Router), React `19.0.0`, TypeScript `5.7.0`, CSS puro com tokens CSS em `globals.css` (sem Tailwind/MUI) | `apps/web/src/app/{layout.tsx,page.tsx,globals.css}`, `apps/web/src/lib/{api.ts,supabase.ts}` |
| **Auth Browser** | `@supabase/supabase-js ^2.49.0` (JWT passado no header `Authorization: Bearer`) | `apps/web/src/lib/supabase.ts` |
| **Backend API** | FastAPI `>=0.115`, Pydantic v2 `>=2.9`, `X-Workspace-Id` header, envelope `AppError` | `apps/api/{main.py,config.py,dependencies.py}`, `apps/api/routes/sp01..sp24.py` |
| **Domínio & Ports** | Python dataclasses + Protocols em `core/`, erros padronizados em `core/errors.py` | `core/{workspaces,channels,jobs,analytics,research,generation,knowledge,opportunities,editorial,darkforge_gateway}/` |
| **Persistência** | PostgREST com JWT do usuário (`SupabaseRestClient`) + `psycopg 3` direto para transações/worker (`DATABASE_URL`) | `adapters/supabase_db/*.py` |
| **Fila & Workers** | Postgres `public.jobs` (`FOR UPDATE SKIP LOCKED`, lease + `fencing_token`, `job_attempts`, `job_events`, `outbox_events`, `idempotent_effects`) | `migrations/0004_sp02_jobs_outbox_storage.sql`, `core/jobs/service.py`, `workers/runner.py` |
| **Roteador IA** | `AIProviderRouter` com proteção contra prompt injection (`wrap_untrusted_context`), redação de segredos e consentimento explícito para externo | `adapters/ai_providers/router.py` |
| **Migrations** | Arquivos SQL sequenciais `0001_*.sql`..`0014_*.sql` aplicados via `scripts/db/apply_migrations.py` (`app.schema_migrations` com SHA-256) | `migrations/`, `scripts/db/apply_migrations.py` |
| **Helpers RLS** | Schema `app`: `app.is_workspace_member(uuid)`, `app.has_workspace_role(uuid, text[])`, `app.set_updated_at()`, `app.forbid_mutation()` | `migrations/0001_*.sql`, `migrations/0002_*.sql` |
| **Testes** | `pytest` (unit, contracts, integration `live_supabase`, e2e), `unittest` (contracts), `tsc --noEmit` & `next build` | `tests/{unit,contracts,integration,e2e}/` |

---

## 2. Inventário e Decisões de Schema (`schema-reference.sql` vs Existente)

| Tabela de Referência | Decisão | Adaptação ao Schema Existente |
|---|---|---|
| `studio_rooms` | **Criar** | Catálogo global (`sala_dados`, `pesquisa`, `mesa_agentes`, `gravacao`, `design_thumbnail`, `estrategia_publicacao`), RLS `SELECT TO authenticated USING (true)`. |
| `agent_definitions` | **Criar** | Catálogo global dos 8 agentes (`dados`, `pesquisa`, `estrategia`, `titulos`, `roteiro`, `thumbnail`, `edicao`, `publicacao`), `contract_version = 1`. |
| `channel_agents` | **Criar** | Equipe por canal com FK composta `(workspace_id, channel_id) -> channels(workspace_id, id)`. Trigger `trg_channels_seed_agents` + backfill idempotente criam os 8 agentes por canal. |
| `content_items` | **Criar** | Vídeo percorrendo o studio; liga opcionalmente a `public.opportunities(workspace_id, id)` e `public.episode_briefs(workspace_id, id)` (SP-07). Não substitui `editorial_calendar_items`, que permanece para o calendário SP-07. |
| `agent_runs` | **Criar** | Liga `job_id` por FK composta `(workspace_id, job_id) -> public.jobs(workspace_id, id)`. **Nenhuma fila nova é criada.** |
| `agent_events` | **Criar** | Feed semântico append-only do studio (`id bigint identity`, `unique(run_id, seq)`), separado de `job_events` (técnico de lease/checkpoint). `REVOKE INSERT/UPDATE/DELETE` para `authenticated` — escrita exclusiva do worker/backend. |
| `agent_outputs` | **Criar** | Versões JSON validadas contra contratos Pydantic v1; `unique(content_item_id, output_type, version)`. Escrita exclusiva do worker/backend (exceto nova versão de revisão humana via RPC/serviço autenticado com `author_kind='human'`). |
| `agent_output_sources` | **Criar** | Proveniência normalizada dos `agent_outputs` (complementa `evidence_links` do SP-07). |
| `agent_handoffs` | **Criar** | Passagem de bastão entre agentes por `content_item`. |
| `approvals` | **Criar** | Registro auditável unificado (`target_kind` in `agent_output`, `opportunity`, `brief`, `publication_plan`), `decided_by = auth.uid()` e imutabilidade (`app.forbid_mutation()`). Coexiste com `opportunity_feedback` e `brief_decision_history` (SP-07). |
| `v_studio_agent_state`, `v_studio_room_state`, `v_content_pipeline` | **Criar (Views)** | Criadas com `WITH (security_invoker = true)` para respeitar RLS. Heartbeat > 2 min em `working` resulta em `no_signal`. |

### Adaptações de Segurança (RLS)
- Toda policy usa `app.is_workspace_member(workspace_id)` e `app.has_workspace_role(workspace_id, ARRAY['owner','editor'])` (em vez de `public.is_workspace_member` do SQL de referência).
- Todas as tabelas recebem `ENABLE ROW LEVEL SECURITY`, `FORCE ROW LEVEL SECURITY` e `REVOKE ALL FROM PUBLIC, anon`.
- `agent_runs`, `agent_events`, `agent_outputs`, `agent_output_sources`, `agent_handoffs` concedem apenas `SELECT` ao papel `authenticated` (navegador nunca escreve diretamente).

---

## 3. Disponibilidade dos Agentes por SP

| Agente | Sala | Depende de | Disponível? | Observação |
|---|---|---|---|---|
| `dados` | `sala_dados` | SP-03 (`analytics`) | **Sim** | Lê `metric_snapshots` e `sync_cursors`. Sem OAuth real ou dados sincronizados, retorna métricas com `availability: "unknown"` e `value: null`. |
| `pesquisa` | `pesquisa` | SP-04/10..18 (`research`) | **Sim** | Lê `reference_videos`, `studio_trend_terms`, `studio_outlier_videos`, `google_trends_validations`. |
| `estrategia` | `mesa_agentes` | SP-06/07 (`knowledge`, `opportunities`) | **Sim** | Consome handoffs de `dados` + `pesquisa` e gera `opportunity` (`requires_approval = true`). |
| `titulos` | `mesa_agentes` | SP-05 (`title_thumbnail`) | **Sim** | Analisa padrões e gera `title_options` com checagem de similaridade (`ORIGINALITY_SIMILARITY_BLOCKED`). |
| `roteiro` | `mesa_agentes` | SP-06/07 (`knowledge`, `editorial`) | **Sim** | Usa RAG L2/L3 + perfil do canal; gera `script_draft`. |
| `thumbnail` | `design_thumbnail` | SP-05 (`title_thumbnail`) | **Sim** | Gera `thumbnail_concepts` com `vision_available = false` quando provedor de visão não configurado. |
| `edicao` | `gravacao` | SP-08 (`darkforge_gateway`) | **Condicional (Desabilitado por padrão se `DARKFORGE_CORE_PATH` ausente)** | Contrato e gateway SP-08 existem; na ausência do executável externo `DARKFORGE_CORE_PATH`, fica `enabled=false` no seed padrão (sala mostra "Módulo DarkForge indisponível") e pode ser habilitado em canais com executor ou em testes determinísticos. |
| `publicacao` | `estrategia_publicacao` | SP-07 (`editorial`) | **Sim** | Gera `publication_plan` (`requires_human_publish = true`). Nunca publica no YouTube. |

---

## 4. Rota da Tela e Arquitetura de Runtime

- **Rota principal do Studio UI:** `/studio` (`apps/web/src/app/studio/page.tsx`) renderizando `<StudioWorkspace />`, acessível também pela navegação principal de `/` ("Estúdio de Conteúdo").
- **API:** Novo router FastAPI `apps/api/routes/studio.py` sob `/api/v1/studio/...`, protegido por `get_current_user`, `get_workspace_id` e `enforce_origin`.
- **Worker:** Novo handler `agent.execute` registrado no `JobWorker` único (`workers/runner.py` + `workers/agents/handler.py`). Usa `claim_next_job`, `heartbeat_job`, `checkpoint_job` e transação atômica com verificação de `fencing_token` para persistir `agent_outputs`, `agent_output_sources`, `agent_events`, `agent_handoffs` e `agent_runs`.
- **Eventos em Tempo Real:** Snapshot inicial via `GET /api/v1/studio/channels/{channel_id}/snapshot`, replay via `GET /api/v1/studio/channels/{channel_id}/events?after_id=...`, e streaming SSE + Supabase Realtime como transporte com fallback automático por cursor.

---

## 5. Riscos e Mitigações

1. **Divergência entre schema de referência e RLS do projeto:** Mitigado usando `app.is_workspace_member` e FKs compostas `(workspace_id, ...)`.
2. **DarkForge core ausente no ambiente local:** Mitigado marcando `edicao` como módulo indisponível quando `DARKFORGE_CORE_PATH` não estiver configurado, sem simular sucesso falso.
3. **Execução de testes sem GPU dedicada:** Todos os agentes suportam provedor determinístico/local via `AIProviderRouter` e política configurável por canal, respeitando consentimento explícito para envio externo (ADR-007).
