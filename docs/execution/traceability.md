# Rastreabilidade — PRD, arquitetura, execução e testes

Este arquivo impede que um requisito desapareça durante a implementação. A IDE deve atualizar a coluna de evidência sem remover IDs.

**Estados:** `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED`, `DONE`, `REJECTED_WITH_REASON`.  
**Regra:** `DONE` exige código/configuração, teste e evidência de aceite.

## 1. Cobertura dos requisitos do PRD

| Requisito | Subplano/tarefas principais | Teste mínimo | Estado | Evidência |
|---|---|---|---|---|
| AUTH-001 | SP-01 | Sessão ausente/inválida não acessa dados | DONE | `adapters/supabase_auth/jwt_verifier.py` (`ES256`/`HS256`), `test_unauthenticated_and_expired_token_blocked` + `test_two_users_two_workspaces_rls_and_api_isolation` OK |
| AUTH-002 | SP-01 | Troca de workspace e canal mantém contexto | DONE | `WorkspaceService`, `X-Workspace-Id`, UI `apps/web/src/app/page.tsx` (`pnpm build:web` OK), `test_two_users_two_workspaces_rls_and_api_isolation` OK |
| AUTH-003 | SP-01, SP-09 | Dois workspaces em UI, API, RPC, busca e Storage | DONE | Validado ao vivo para API/Postgres RLS/RPC/Storage/RAG/Editorial/Restore (`test_sp01_live_rls.py`, `test_sp02_live_jobs_and_storage.py`, `test_sp06_live_rag.py`, `test_sp07_live_editorial.py`, `test_sp09_e2e_and_restore.py` OK) |
| AUTH-004 | SP-01, SP-03 | Logout/revogação OAuth são independentes | DONE (infra); BLOCKED (OAuth real) | Sessão Supabase e tabela `platform_connections`/`disconnect` desacopladas (`MockTransport` OK); revogação OAuth Google real aguarda credenciais |
| AUTH-005 | SP-01, SP-03 | Logout e revisão de conexões | DONE | Logout em `apps/web/src/app/page.tsx` + listagem/desconexão em Configurações e `SP-03` |
| AUTH-006 | SP-01, SP-03 | Vazio, permissão e erro têm estados distintos | DONE | `ErrorEnvelope`, `test_cross_workspace_isolation_never_returns_empty`, `test_supabase_outage_is_explicit_503_and_health_degraded`, `test_sp01_live_rls.py` (403 vs `[]`) OK |
| CH-001 | SP-01 | CRUD e validação do Channel Profile | DONE | `ChannelService`, `routes/sp01.py`, UI `page.tsx`, `test_sp01_live_rls.py` OK |
| CH-002 | SP-01 | Público, voz, pilares e restrições persistem | DONE | `channel_profile_versions` + `ChannelProfilePayload` + `test_sp01_workspace_and_channels.py` OK |
| CH-003 | SP-01 | Edição cria versão e preserva recomendação antiga | DONE | Trigger `trg_profile_versions_immutable` + `test_sp01_live_rls.py` (v1 preservada após v2) OK |
| CH-004 | SP-01 | Mudança de tema tem data e histórico | DONE | `editorial_theme_changes` + `test_sp01_live_rls.py` (`Tema V1` -> `Tema V2`) OK |
| CH-005 | SP-03 | OAuth, escopos, refresh e revogação | IN_PROGRESS | Implementado em `OfficialYouTubeAdapter` + `TokenVault` + `0005` (`T-YT-001` OK com `MockTransport`); falta canal OAuth Google real |
| CH-006 | SP-03 | Sync incremental/backfill e cursor | IN_PROGRESS | `commit_sync_unit` atômico + `sync_cursors` (`T-YT-002` OK ao vivo no Postgres + `MockTransport`) |
| CH-007 | SP-03 | Frescor e erro parcial visíveis | DONE | `SyncCursorView`, `freshness_status`, `partial_errors_json` exibidos no Analytics Center |
| CH-008 | SP-03 | Desconexão explica retenção e impacto | DONE | `disconnect_connection(keep_readonly|purge_synced_data)` + UI + teste vivo OK |
| AN-001 | SP-03 | Dashboard de portfólio com filtros | DONE | `GET /api/v1/analytics/portfolio` + UI Analytics Center |
| AN-002 | SP-03 | Dashboard de canal por período/formato/pilar | DONE | `GET /api/v1/channels/{id}/analytics` + UI Analytics Center |
| AN-003 | SP-03 | Ficha de vídeo com dados e histórico | DONE | `GET /api/v1/videos/{id}` + ficha na UI + `test_sp03_live_youtube_analytics.py` OK |
| AN-004 | SP-03 | Unknown/parcial/atrasado não viram zero | DONE | `MetricFactInput.__post_init__`, SQL `chk_unavailable_has_null_value`, UI badges `UNKNOWN`, teste OK |
| AN-005 | SP-03 | Fonte, semântica, período e atualização | DONE | `metric_definitions` + `MetricFactView` (`source`, `source_revision`, `period_start..end`) |
| AN-006 | SP-03 | Comparação incompatível é bloqueada/sinalizada | DONE | `assert_compatible_comparison` + `test_incompatible_comparison_blocked` OK |
| AN-007 | SP-03 | Revisões preservam histórico | DONE | `source_revision` incremental preservando v1 após v2 (`test_sp03_live_youtube_analytics.py` OK) |
| RES-001 | SP-04 | Research run guarda objetivo e filtros | DONE | `research_runs` + `POST /api/v1/research/runs` + `test_sp04_sp05_live.py` OK |
| RES-002 | SP-04 | Candidato explica similaridade | DONE | `compute_channel_similarity` + `similarity_factors_json` + `test_sp04_sp05_research_title_thumb.py` OK |
| RES-003 | SP-04 | Evidência abre fonte e snapshot | DONE | `canonical_url`, `source_origin`, `snapshot_observed_at` + `GET /api/v1/research/runs/{id}` OK |
| RES-004 | SP-04 | Aprovar/rejeitar/arquivar/anotar | DONE | `POST /api/v1/research/references/{id}/curate` + UI Research + `test_sp04_sp05_live.py` OK |
| RES-005 | SP-04 | Quota e prioridade entre research e sync | DONE | `ResearchService` usa `QuotaPool.PUBLIC_RESEARCH`; `T-YT-003` validou prioridade de `own_sync` |
| RES-006 | SP-04 | Público não é apresentado como privado | DONE | `scope_notice` explícito na API/UI; zero campos privados em `reference_videos` |
| RES-007 | SP-04 | Retry idempotente e deduplicação | DONE | `idempotency_key` + `UNIQUE(workspace_id, platform, external_video_id)` (`test_sp04_sp05_live.py` OK) |
| TITLE-001 | SP-05 | Golden dataset de estrutura de títulos | DONE | `analyze_title_structure` + `test_title_thumbnail_golden_dataset_cases` OK |
| TITLE-002 | SP-05 | Alternativas com canal, fontes e diferenciação | DONE | `generate_original_title_alternatives` + UI + teste unitário OK |
| THUMB-001 | SP-05 | OCR/visão com resultado e incerteza | DONE | `thumbnail_analyses` (`is_probabilistic=true`, `limitations_json`) |
| THUMB-002 | SP-05 | Padrões visuais e direção diferenciada | DONE | `differentiation_notes` + checagem de direitos em `thumbnail_assets` |
| THUMB-003 | SP-05 | Visão indisponível não inventa análise | DONE | `vision_status='unavailable'`, `ocr_text=None` (`test_vision_unavailable_never_invents_ocr_and_ssrf_blocked` + teste vivo OK) |
| ORIG-001 | SP-05 | Similaridade alta exige revisão | DONE | `check_originality` + `ORIGINALITY_SIMILARITY_BLOCKED` + golden `TT-002` OK |
| KNOW-001 | SP-06 | Importação com origem, direitos e metadados | DONE | `knowledge_sources`, `KnowledgeService.import_source`, `POST /api/v1/knowledge/sources` (`test_sp06_live_rag.py` OK) |
| KNOW-002 | SP-06 | Curadoria L0–L3 e uso permitido | DONE | `review_source`, check `L0..L3` + `allowed_in_generation` (`test_sp06_live_rag.py` OK) |
| KNOW-003 | SP-06 | Reimportação deduplica e versiona | DONE | `content_sha256` deduplication + `source_version` (`test_sp06_live_rag.py` OK) |
| KNOW-004 | SP-06 | L0/arquivada não entra em novas buscas | DONE | `knowledge_repo.search_hybrid` filtra `status='INDEXED'` e exclui `L0`/`ARCHIVED` (`test_sp06_live_rag.py` OK) |
| KNOW-005 | SP-06 | Filtros e RLS antes do contexto | DONE | `p_knowledge_*` RLS + filtros workspace/canal/idioma/direitos antes de montar prompt (`T-RAG-001` OK) |
| KNOW-006 | SP-06 | Citações abrem chunks/fontes usados | DONE | `generations.citations_json` + `retrieval_runs` (`test_sp06_live_rag.py` OK) |
| KNOW-007 | SP-06 | Exclusão cobre chunks, embeddings e arquivos | DONE | `delete_source` remove source/chunks/embeddings em cascade e invalida cache (`test_sp06_live_rag.py` OK) |
| KNOW-008 | SP-06, SP-09 | Recall, citação, arquivamento e rebuild | DONE | `rag_security_golden.jsonl` + `rebuild_embeddings` nova `EmbeddingRevision` (`T-RAG-002` OK) |
| OPP-001 | SP-07 | Geração usa perfil, pesquisa e RAG permitidos | DONE | `OpportunityService.generate_opportunities`, `load_generation_context` + RAG L2/L3 (`test_sp07_live_editorial.py` OK) |
| OPP-002 | SP-07 | Score, confiança, versão e limitações | DONE | `compute_opportunity_score` (`v1.0.0`), `score_breakdown_json`, `confidence`, `limitations_json` |
| OPP-003 | SP-07 | Tema, ângulo e diferenciação | DONE | 4 contratos de analistas especializados + `differentiation` (`test_sp07_live_editorial.py` OK) |
| OPP-004 | SP-07 | Aprovar/rejeitar/editar/arquivar com histórico | DONE | `review_opportunity` + `opportunity_feedback` imutável (`trg_opportunity_feedback_immutable`) |
| OPP-005 | SP-07 | Feedback sem alegar fine-tuning | DONE | `fine_tuning_claimed=False`, `feedback_mode="editorial_audit_only"` (`test_sp07_opportunities_and_editorial.py` OK) |
| OPP-006 | SP-07 | Dados insuficientes geram incerteza | DONE | `insufficient_data=True`, `confidence<=0.35`, `limitations_json` explícito (`test_sp07_opportunities_and_editorial.py` OK) |
| EDIT-001 | SP-07 | Brief referencia oportunidade e fontes | DONE | `episode_briefs.opportunity_id/profile_version_id/source_refs_json` (`test_sp07_live_editorial.py` OK) |
| EDIT-002 | SP-07 | Campos editáveis e validados | DONE | `update_draft` em `DRAFT`/`IN_REVIEW` + validação `title/hook/angle` |
| EDIT-003 | SP-07 | Aprovação congela; edição cria versão | DONE | `trg_episode_briefs_freeze` + API `409 VERSION_CONFLICT` + `create_new_version` v1->v2 (`T-ED-001` OK) |
| EDIT-004 | SP-07 | Exportação com versão e fontes | DONE | `GET /api/v1/briefs/{id}/export` (`markdown`/`json`/`csv`) com SHA-256 + `source_refs` (`test_sp07_live_editorial.py` OK) |
| EDIT-005 | SP-07 | Calendário sem publicação automática | DONE | `editorial_calendar_items` `CHECK (auto_publish_enabled = false)` + rejeição `422` (`test_sp07_live_editorial.py` OK) |
| EDIT-006 | SP-07 | Histórico de decisões auditável | DONE | `brief_decision_history` com trigger imutável (`CREATE`, `APPROVE`, `CREATE_VERSION`, `EXPORT`) |
| PROD-001 | SP-08 | Só brief aprovado vira intenção idempotente | DONE | `ProductionIntentService.create_production_intent` + `POST /api/v1/briefs/{id}/production` (`test_sp08_live_production_contract.py` OK) |
| PROD-002 | SP-08 | Progresso e artifacts reais | BLOCKED | Infra de job/gateway pronta; execução real bloqueada sem código-fonte `DARKFORGE_CORE_PATH` (`503 DARKFORGE_UNAVAILABLE`) |
| PROD-003 | SP-08 | Pausa/retomada/cancelamento confirmados | BLOCKED | Semântica real implementada no `CommandBus`/`jobs` (SP-02); acoplamento com executor externo aguarda `DARKFORGE_CORE_PATH` |
| PROD-004 | SP-08 | Single-writer e reconciliação | DONE | `docs/adr/ADR-016-darkforge-single-writer.md` + `public.production_intents`/`jobs` como verdade única |
| PROD-005 | SP-08 | Manifest/checksum/ready antes de concluir | DONE | Constraint `chk_ready_requires_validated_manifest` + `complete_with_validated_manifest` (`test_sp08_darkforge_gateway.py` e live OK) |
| JOB-001 | SP-02 | Fila e histórico com filtros | DONE | `GET /api/v1/jobs`, filtros por estado/tipo, UI Jobs em `apps/web/src/app/page.tsx`, `test_live_queue...` OK |
| JOB-002 | SP-02 | Progresso por etapas reais | DONE | `checkpoint_job`, `completed_steps/total_steps`, `job_events`, `test_sp02_jobs_and_storage.py` OK |
| JOB-003 | SP-02 | Solicitação versus efeito de controle | DONE | `request_pause`/`request_cancel` diferenciando pedido pendente de confirmação (`pause_requested_pending_checkpoint` vs `pause_applied`) |
| JOB-004 | SP-02 | Reinício e recovery sem duplicidade | DONE | `app.reconcile_expired_leases()`, `idempotent_effects`, `test_worker_crash_recovery_fencing_and_sse_replay` + `test_sp02_live_jobs_and_storage.py` OK |
| JOB-005 | SP-02 | Erro acionável e retry | DONE | `error_code`, `error_message`, `retryable`, `compute_backoff_seconds`, exibidos na UI Jobs |
| JOB-006 | SP-02 | Rede/Supabase/quota/modelo bloqueiam sem sucesso | DONE | `JobWorker` transiciona indisponibilidade para `BLOCKED`; API retorna `503 SUPABASE_UNAVAILABLE` |
| JOB-007 | SP-09 | Diagnóstico com redaction | DONE | `scripts/diagnostics/export_diagnostics.py`, `GET /api/v1/diagnostics/export`, UI Configuracoes (`test_sp09_e2e_and_restore.py` OK) |
| JOB-008 | SP-09 | Backup/restore de dados e arquivos | DONE (lógico + Storage) | `scripts/backup/backup_and_restore.py` + `docs/runbooks/backup-and-restore.md` validado ao vivo (`test_sp09_e2e_and_restore.py` OK) |

## 2. Cobertura dos ADRs da arquitetura

| ADR | Decisão que precisa permanecer verdadeira | Subplano | Estado/evidência |
|---|---|---|---|
| ADR-001 | Web UI local; EXE apenas launcher opcional | SP-01, SP-09 | DONE (Web UI Next.js local construída; EXE launcher opcional não exigido) |
| ADR-002 | Monólito modular e workers, não microserviços | SP-01, SP-02 | DONE (`apps/api`, `core/*`, `adapters/*`, `workers/*` validados nos contratos arquiteturais) |
| ADR-003 | Command Bus e Job Manager compartilhados | SP-02, SP-08 | DONE (CommandBus + fila única `jobs` + `ProductionIntentService` sem executor paralelo) |
| ADR-004 | Supabase como fonte única; sem segunda verdade SQLite | SP-01, SP-02, SP-08 | DONE (Postgres Supabase + `ADR-016`; zero leitura/escrita em SQLite paralelo) |
| ADR-005 | APIs oficiais e limites para dados públicos | SP-03, SP-04 | BLOCKED (OAuth real) / DONE (QuotaLedger + `MockTransport` + escopo público/privado) |
| ADR-006 | RAG com curadoria/proveniência, sem fine-tuning | SP-06 | DONE (`KnowledgeService`, L0–L3, `generations`, zero fine-tuning) |
| ADR-007 | Provider Router sem fallback externo silencioso | SP-06, SP-07 | DONE (`AIProviderRouter` + `OpportunityService` exigem consentimento explícito para provider externo) |
| ADR-008 | Aprovação humana para brief e produção | SP-07, SP-08 | DONE (`trg_episode_briefs_freeze` + `ProductionIntentService` exige `APPROVED`) |
| ADR-009 | Versionamento de perfil, prompts, scores, fontes e embeddings | Todos | DONE (`ChannelProfileVersion`, `KnowledgeSource`, `EmbeddingRevision`, `Opportunity.score_version`, `EpisodeBrief.version` validados ao vivo) |
| ADR-010 | pgvector como projeção reconstruível e autorizada | SP-06 | DONE (`embedding_revisions`, `knowledge_embeddings`, `rebuild_embeddings` testado ao vivo) |
| ADR-011 | Supabase Auth, memberships e RLS | SP-01 | DONE (`T-SEC-001` e `T-SEC-002` aprovados ao vivo em SP-01..SP-09) |
| ADR-012 | Storage privado; filesystem só temporário/cache | SP-02 | DONE (`SupabaseStorageClient`, buckets privados, SHA-256, `READY`, reconciler validados em `T-STO-001` e `T-REL-001`) |
| ADR-013 | Fila com lease, fencing, outbox e idempotência | SP-02 | DONE (`FOR UPDATE SKIP LOCKED`, `fencing_token`, `outbox_events`/`inbox_events`, `idempotent_effects` validados em `T-JOB-001..003`) |
| ADR-014 | Backup/PITR/Storage e restore com RPO/RTO | SP-09 | DONE (lógico/Storage: `backup_and_restore.py` + `docs/runbooks/backup-and-restore.md` validado em `T-REL-001`) |
| ADR-015 | Rede indisponível em modo degradado sem sucesso falso | SP-02, SP-09 | DONE (503 `SUPABASE_UNAVAILABLE` + banner degradado + worker `BLOCKED`) |
| ADR-016 | Estratégia Single-Writer DarkForge sem executor paralelo | SP-08 | DONE (`ADR-016-darkforge-single-writer.md` + `production_intents` + `503 DARKFORGE_UNAVAILABLE`) |
| ADR-017 | Automação assistida Playwright no Studio Trends (emenda ADR-005) | SP-10..SP-14 | DONE (`ADR-017-studio-assisted-browser.md`, sessão persistente + Human-in-the-Loop, rate-limit, Outlier Engine) |

## 3. Catálogo de testes obrigatórios

| Teste | Cenário | Gate |
|---|---|---|
| T-SEC-001 | Dois usuários/workspaces tentam ler/alterar dados, RPCs, buscas e arquivos cruzados | SP-01/SP-09 (`DONE`: `test_sp01_live_rls.py`, `test_sp02_live_jobs_and_storage.py`, `test_sp06_live_rag.py`, `test_sp07_live_editorial.py`, `test_sp09_e2e_and_restore.py` PASSOU) |
| T-SEC-002 | Backend privilegiado e RPC `security definer` exigem escopo e `search_path` seguro | SP-01/SP-09 (`DONE`: `test_sp01_migrations_and_security.py` + testes vivos OK) |
| T-JOB-001 | Dois workers disputam jobs; somente um claim válido | SP-02 (`DONE`: `test_sp02_live_jobs_and_storage.py` PASSOU) |
| T-JOB-002 | Lease expira; fencing impede commit de worker antigo | SP-02 (`DONE`: `test_sp02_live_jobs_and_storage.py` PASSOU) |
| T-JOB-003 | Crash depois do efeito externo e antes do commit; retry reconcilia | SP-02 (`DONE`: `test_sp02_live_jobs_and_storage.py` PASSOU) |
| T-JOB-004 | Supabase/rede cai durante sync e upload; `BLOCKED/RECOVERABLE`, sem sucesso | SP-02/SP-09 (`DONE`: `test_supabase_outage_is_explicit_503_and_health_degraded` + `JobWorker` PASSOU) |
| T-STO-001 | Upload interrompido, checksum, manifest `ready` e órfãos | SP-02 (`DONE`: `test_sp02_live_jobs_and_storage.py` + `test_sp09_e2e_and_restore.py` PASSOU) |
| T-YT-001 | OAuth refresh, expiração e revogação | SP-03 (`DONE` com `MockTransport`; `BLOCKED` para canal OAuth Google real) |
| T-YT-002 | Retry de página; cursor e fatos não duplicam nem pulam | SP-03 (`DONE`: `test_sp03_live_youtube_analytics.py` PASSOU) |
| T-YT-003 | Quota de research não impede sync prioritário | SP-03/SP-04 (`DONE`: `test_sp03_live_youtube_analytics.py` PASSOU) |
| T-AN-001 | Métrica ausente, parcial, tardia e revisada | SP-03 (`DONE`: `test_sp03_live_youtube_analytics.py` PASSOU) |
| T-RES-001 | Evidência pública rastreável e distinta de analytics privado | SP-04 (`DONE`: `test_sp04_sp05_live.py` PASSOU) |
| T-RAG-001 | Retrieval respeita workspace/canal/direitos e cita fontes | SP-06 (`DONE`: `test_sp06_live_rag.py` PASSOU) |
| T-RAG-002 | Arquivar/excluir/trocar embedding e rebuild | SP-06 (`DONE`: `test_sp06_live_rag.py` PASSOU) |
| T-AI-001 | Fallback externo bloqueado sem consentimento; prompt injection tratado como dado | SP-06/SP-07 (`DONE`: `test_sp06_rag_and_router.py`, `test_sp07_live_editorial.py` PASSOU) |
| T-ED-001 | Aprovação congela brief e edição cria nova versão | SP-07 (`DONE`: `test_sp07_live_editorial.py` + `trg_episode_briefs_freeze` PASSOU) |
| T-DF-001 | Produção, crash, retry, artifact e single-writer | SP-08 (`DONE` contrato/gate `APPROVED`/idempotência/`503 DARKFORGE_UNAVAILABLE`; `BLOCKED` execução real sem código DarkForge) |
| T-REL-001 | Instalação limpa, upgrade e restore completo | SP-09 (`DONE` lógico/Storage: `test_live_e2e_diagnostics_redaction_and_isolated_backup_restore` PASSOU) |
| T-E2E-001 | Fluxo completo do PRD, incluindo falhas e recuperação | SP-09 (`DONE` fluxo interno completo; `BLOCKED` apenas nos passos OAuth YouTube real e execução DarkForge real) |

## 4. Auditoria de órfãos

Antes de cada gate e na entrega final, verificar:

- todo requisito MVP tem pelo menos uma tarefa e um teste;
- toda tarefa aponta para requisito ou ADR;
- todo teste obrigatório tem resultado ou bloqueio explícito;
- todo risco arquitetural tem mitigação implementada ou pendência aberta;
- nenhum item foi marcado `DONE` apenas porque uma tela existe;
- nenhum requisito foi apagado da matriz.
