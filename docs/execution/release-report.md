# Relatório Final de Release — DarkForge Channel OS (`SP-00`..`SP-09`)

- **Data:** 2026-11-16
- **Decisão de Release:** **`NOT_READY`** para piloto completo com publicação externa/vídeo ao vivo (infraestrutura, banco Supabase, Auth/RLS, Workers/Storage, Analytics/Research com transporte HTTP gravado, RAG pgvector+FTS, Opportunities/Editorial, Gateway Single-Writer DarkForge e Backup/Restore E2E concluídos com **45/45 testes passando**; restam **2 bloqueios externos** documentados abaixo).

---

## 1. Resumo do que foi concluído (`DONE`) por subplano

| Subplano | Escopo concluído | Evidência principal |
|---|---|---|
| `SP-00` | Fundações, ADRs (`ADR-001..015`), contratos JSON Schema/events, golden datasets (`title_thumbnail_golden.jsonl`, `rag_security_golden.jsonl`), catálogo de métricas, protótipo navegável e auditoria DarkForge | `docs/adr/`, `contracts/`, `python -m unittest discover -s tests/contracts -v` (**5/5 OK**) |
| `SP-01` | Workspaces, Auth JWT (`ES256`/`HS256`), `ChannelProfileVersion` imutável, `EditorialThemeChange`, RLS + `FORCE ROW LEVEL SECURITY`, Next.js UI inicial | `migrations/0001..0003`, `core/{workspaces,channels}`, `tests/integration/test_sp01_live_rls.py` OK |
| `SP-02` | Fila única Postgres (`SKIP LOCKED`), heartbeat, lease expiry, fencing token, `outbox_events`/`inbox_events`, `idempotent_effects`, Storage privado com SHA-256/`READY` e reconciler | `migrations/0004`, `core/jobs`, `workers/runner.py`, `adapters/supabase_storage`, `test_sp02_live_jobs_and_storage.py` OK |
| `SP-03` | TokenVault (`AES-256-GCM`), adapter oficial YouTube (`MockTransport`), `QuotaLedger` com reserva `own_sync`, `sync_cursors` transacional, semântica `unknown != 0` e revisões `source_revision` | `migrations/0005..0006`, `core/analytics`, `adapters/youtube`, `test_sp03_live_youtube_analytics.py` OK (infra/Postgres) |
| `SP-04` & `SP-05` | Research Explorer público rastreável (curadoria, deduplicação, separação explícita de analytics privado), Title/Thumbnail Intelligence (`vision_status='unavailable'` honesto, `ORIGINALITY_SIMILARITY_BLOCKED`) e golden dataset | `migrations/0007`, `core/research`, `core/generation/title_thumbnail.py`, `test_sp04_sp05_live.py` OK |
| `SP-06` | Knowledge/RAG Studio (L0–L3, chunking semântico Hook/Body/CTA, deduplicação SHA-256, `pgvector` + FTS GIN, citações, arquivamento/exclusão, rebuild `EmbeddingRevision`) e `AIProviderRouter` com consentimento explícito e proteção contra prompt injection | `migrations/0008`, `core/knowledge`, `adapters/ai_providers/router.py`, `test_sp06_live_rag.py` OK |
| `SP-07` | Opportunity Engine (4 analistas especializados, fórmula versionada `v1.0.0`, tratamento de dados insuficientes `OPP-006`, feedback sem fine-tuning `OPP-005`) e Editorial Studio (`EpisodeBrief` congelável por trigger SQL + API, versões `v1->v2`, export Markdown/JSON/CSV, calendário manual sem auto-publicação) | `migrations/0009`, `core/{opportunities,editorial}`, `test_sp07_live_editorial.py` OK |
| `SP-08` (Gateway) | Estratégia single-writer (`ADR-016`), `production_intents`, validação de `EpisodeBrief.status = 'APPROVED'`, idempotência, validação `manifest_validated = true` + SHA-256 no Storage e bloqueio explícito `503 DARKFORGE_UNAVAILABLE` sem executor simulado | `docs/adr/ADR-016-darkforge-single-writer.md`, `migrations/0010`, `core/darkforge_gateway`, `adapters/darkforge`, `test_sp08_live_production_contract.py` OK |
| `SP-09` | Telemetria allowlisted (`core/telemetry.py`), pacote de diagnóstico com redaction (`JOB-007`), backup lógico `REPEATABLE READ` + Storage e restore em workspace isolado (`JOB-008`, `T-REL-001`), runbook RPO/RTO e suíte E2E | `scripts/diagnostics/export_diagnostics.py`, `scripts/backup/backup_and_restore.py`, `routes/sp09.py`, `docs/runbooks/backup-and-restore.md`, `tests/e2e/test_sp09_e2e_and_restore.py` OK |

---

## 2. Itens bloqueados (`BLOCKED`) e dependências externas faltantes

1. **YouTube OAuth Real (`SP-03` Gate G3 / `SP-04` YouTube Data API ao vivo):**
   - **Falta:** `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET` válidos (Google Cloud Console) e um canal YouTube de teste autorizado via fluxo OAuth real.
   - **Estado atual:** Vault `AES-256-GCM`, state OAuth CSRF, refresh, revogação, `QuotaLedger` e sync transacional estão validados ao vivo no Postgres usando `httpx.MockTransport`.
2. **Núcleo Executor DarkForge (`SP-08` Gate G8 / `PROD-002` & `PROD-003` em execução real):**
   - **Falta:** Código-fonte ou runtime executável do motor DarkForge (`DARKFORGE_CORE_PATH`). Foram encontrados apenas manifests históricos em `C:\Users\brend\Documents\DarkForge\job_*\manifest.json`.
   - **Estado atual:** Gate `APPROVED -> ProductionIntent`, idempotência, linked job e constraint SQL `chk_ready_requires_validated_manifest` funcionam ao vivo; o despacho retorna `503 DARKFORGE_UNAVAILABLE` e marca intent/job como `BLOCKED` sem fabricar renderização ou vídeos falsos.
3. **Observação de ferramenta local:** `psql`/`pg_dump` não estão instalados no PATH do Windows; o backup/restore foi implementado em Python (`scripts/backup/backup_and_restore.py`) usando snapshot Postgres `REPEATABLE READ` + API do Supabase Storage.

---

## 3. Migrations e Banco de Dados (Supabase `pqtwhwjrpgxpagkyxktk`)

Todas as migrations aplicadas via `scripts/db/apply_migrations.py`:
- `0001_sp01_workspace_auth_channels.sql`
- `0002_sp01_rls_and_security.sql`
- `0003_sp01_public_rpc_create_workspace.sql`
- `0004_sp02_jobs_outbox_storage.sql`
- `0005_sp03_youtube_analytics.sql`
- `0006_sp03_allow_workspace_cascade_delete.sql`
- `0007_sp04_sp05_research_title_thumb.sql`
- `0008_sp06_knowledge_rag.sql`
- `0009_sp07_opportunities_briefs_calendar.sql`
- `0010_sp08_production_intents.sql`

---

## 4. Segurança, RLS e Isolamento

- `ENABLE ROW LEVEL SECURITY` e `FORCE ROW LEVEL SECURITY` ativos em todas as tabelas multi-tenant de `public`.
- `REVOKE ALL FROM PUBLIC, anon` aplicado nas tabelas de domínio; tabelas/funções internas de segredo e fila de workers (`platform_connection_secrets`, `oauth_states`, `app.claim_next_job` etc.) revogadas também de `authenticated`.
- Buckets privados (`knowledge`, `references`, `exports`, `production`) com política RLS por prefixo `<workspace_id>/`.
- Diagnósticos (`GET /api/v1/diagnostics/export`) com redaction automático de tokens/secrets e exclusão explícita de segredos OAuth e `content_text` integral.
- Verificado por contratos estáticos (`tests/contracts/test_sp01_migrations_and_security.py`) e testes vivos multi-usuário (`sp01`, `sp02`, `sp06`, `sp07`, `sp09`).

---

## 5. Fila, Storage, Backup e Restore

- Concorrência `FOR UPDATE SKIP LOCKED`, expiração de lease, fencing token (`FENCING_TOKEN_STALE`), `outbox_events`/`inbox_events`, `idempotent_effects` e reconciliação de objetos órfãos/checksum testados ao vivo em `tests/integration/test_sp02_live_jobs_and_storage.py`.
- Backup lógico (`REPEATABLE READ READ ONLY`) + binários de Storage + restore em workspace isolado validados em `tests/e2e/test_sp09_e2e_and_restore.py` preservando SHA-256 de `EpisodeBrief` congelado e integridade byte-a-byte de objetos restaurados.

---

## 6. Provedores de IA, Eval/RAG e Decisão Arquitetural

- **Router local-first sem fallback silencioso:** `AIProviderRouter` usa embedding determinístico CPU local (`local-bow-v1`, 64d) por padrão neste hardware sem GPU dedicada e bloqueia chamadas externas sem consentimento (`412 AI_EXTERNAL_CONSENT_REQUIRED`).
- **Golden Datasets:** `tests/evaluation/datasets/title_thumbnail_golden.jsonl` (`TT-001..005`) e `tests/evaluation/datasets/rag_security_golden.jsonl` executados em pytest.

---

## 7. Resultados de Testes Executados (Estado Final do Repositório)

| Comando | Escopo | Resultado exato |
|---|---|---|
| `.\.venv\Scripts\python.exe -m pytest -v` | Toda a suíte (contratos, unitários, integração viva Supabase/pgvector/Storage/RLS e E2E SP-09) | **45 passed, 0 failed, 0 skipped** (1 StarletteDeprecationWarning, `307.41s`) |
| `.\.venv\Scripts\python.exe -m unittest discover -s tests/contracts -v` | Validação estrutural de ADRs, schemas JSON, golden datasets e `.env.example` | **5/5 OK** (`0.006s`) |
| `pnpm typecheck:web` & `pnpm build:web` | Typecheck TypeScript e build Next.js `15.5.29` do painel `apps/web` | **Exit code 0** (`Route / 76.5 kB`) |

---

## 8. Como subir localmente e operar após fornecer as pendências

1. Preencher no `.env` local (fora do Git): `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, e quando disponível `DARKFORGE_CORE_PATH`.
2. Subir API FastAPI: `.\.venv\Scripts\uvicorn.exe apps.api.main:app --host 127.0.0.1 --port 8000`
3. Subir Web UI Next.js: `pnpm --filter @darkforge/web start` (ou `dev`) em `http://127.0.0.1:3000`.
4. Rodar worker de fila única: `.\.venv\Scripts\python.exe -m workers.runner`
5. Para backup e restore isolado, seguir `docs/runbooks/backup-and-restore.md`.

---

## 9. Veredito Final de Prontidão

- **Status do código, migrations e testes executáveis no ambiente atual:** Implementação completa e verificada (`45/45 pytest`, `5/5 unittest`, `pnpm typecheck:web` + `build:web` OK).
- **Status para Piloto Externo Real (`Gate G9 / Release`):** **`NOT_READY`** até configurar credenciais reais de OAuth YouTube (`Gate G3` ao vivo) e o código-fonte do motor DarkForge em `DARKFORGE_CORE_PATH` (`Gate G8` ao vivo).
