# Contratos de Domínio, API `/api/v1` e Integrações (SP-00-T06)

**Data:** 2026-11-16  
**Schemas JSON:** [v1-envelope.schema.json](../../contracts/api/v1-envelope.schema.json), [domain-events.schema.json](../../contracts/events/domain-events.schema.json), [commands-and-jobs.schema.json](../../contracts/schemas/commands-and-jobs.schema.json)

---

## 1. Regras Transversais da API Local (`/api/v1`)
- Toda rota resolve `user_id` via JWT validado do Supabase Auth e exige `workspace_id` autorizado em `workspace_members`.
- IDs de canal, brief, fonte ou job **nunca** autorizam acesso por si sós (`AUTH-003`, `ADR-011`).
- Comandos longos retornam `202 Accepted` com `AcceptedJobResponse` e respeitam `Idempotency-Key`.
- Erros seguem `ErrorEnvelope` (`code`, `message`, `retryable`, `details`, `correlation_id`, `job_id`).
- `GET /api/v1/jobs/{id}/events` usa SSE com `last_event_id` monotônico; a UI reconstrói estado oficial por `GET /api/v1/jobs/{id}`.
- A UI **nunca** chama FFmpeg/FFprobe, **nunca** recebe `service_role` e **nunca** executa SQL privilegiado.

---

## 2. Rotas `/api/v1`

| Rota | Tipo | Finalidade |
|---|---|---|
| `GET /api/v1/health` | Sync | Status da API local e conectividade com Supabase (sem mascarar outage) |
| `GET /api/v1/workspaces` | Sync | Listar workspaces com membership ativo do usuário |
| `POST /api/v1/workspaces` | Sync | Criar workspace e membership `owner` inicial |
| `GET /api/v1/channels` | Sync | Listar canais do workspace e frescor do último sync |
| `POST /api/v1/channels` | Sync | Criar canal e `ChannelProfileVersion` v1 |
| `PUT /api/v1/channels/{id}/profile` | Sync | Criar nova versão do perfil editorial (sem sobrescrever histórico) |
| `POST /api/v1/connections/youtube/authorize` | Sync | Iniciar fluxo OAuth com `state` e PKCE |
| `DELETE /api/v1/connections/{id}` | Sync | Revogar conexão YouTube e registrar escolha de retenção |
| `POST /api/v1/channels/{id}/sync` | Command (`202`) | Enfileirar sync incremental ou backfill |
| `GET /api/v1/channels/{id}/analytics` | Sync | Consultar métricas normalizadas, origem e `availability` |
| `GET /api/v1/videos/{id}` | Sync | Ficha detalhada do vídeo com histórico de revisões |
| `POST /api/v1/research/runs` | Command (`202`) | Iniciar pesquisa pública com objetivo, filtros e orçamento |
| `GET /api/v1/research/runs/{id}` | Sync | Consultar candidatos, similaridade explicada e snapshots |
| `POST /api/v1/opportunities/generate` | Command (`202`) | Gerar oportunidades a partir de pesquisa, perfil e RAG |
| `POST /api/v1/opportunities/{id}/decision` | Sync | Aprovar, rejeitar, editar ou arquivar com registro de motivo |
| `POST /api/v1/knowledge/sources` | Sync | Importar copy/fonte (`L0`) com metadados, hash e direitos |
| `POST /api/v1/knowledge/sources/{id}/review` | Sync | Atualizar nível `L0–L3`, status e direitos |
| `POST /api/v1/knowledge/reindex` | Command (`202`) | Indexar/reconstruir chunks e `EmbeddingRevision` |
| `POST /api/v1/generations` | Command (`202`) | Gerar título/copy/brief com `ProviderRouter` e citações |
| `GET /api/v1/generations/{id}/provenance` | Sync | Inspecionar fontes, `RetrievalRun`, modelo e versão de prompt |
| `POST /api/v1/briefs` | Sync | Criar `EpisodeBrief` rascunho a partir de oportunidade |
| `POST /api/v1/briefs/{id}/approve` | Sync | Congelar versão aprovada (`APPROVED`) |
| `POST /api/v1/briefs/{id}/production` | Command (`202`) | Enviar `ProductionIntent` (exige brief `APPROVED`) |
| `GET /api/v1/jobs` | Sync | Listar fila e histórico com filtros |
| `GET /api/v1/jobs/{id}` | Sync | Estado oficial e etapas do job |
| `POST /api/v1/jobs/{id}/pause` | Sync | Registrar pedido de pausa em checkpoint seguro |
| `POST /api/v1/jobs/{id}/resume` | Sync | Reenfileirar job pausado/interrompido/recuperável |
| `POST /api/v1/jobs/{id}/cancel` | Sync | Registrar pedido de cancelamento idempotente |
| `GET /api/v1/jobs/{id}/events` | SSE | Stream de progresso com replay por `last_event_id` |
| `GET /api/v1/studio/overview` | Sync | Visão agregada da Sede com todos os canais do workspace, agentes, contadores e item ativo (sem provisionar agentes) |

### Contrato `GET /api/v1/studio/overview`
- **Headers obrigatórios:** `Authorization: Bearer <jwt>`, `X-Workspace-Id: <uuid>`.
- **Permissão:** qualquer membro ativo do workspace (`require_membership`); usuário fora do workspace recebe `403`; token ausente/inválido recebe `401`; workspace inexistente recebe `404`/`403`.
- **Sem efeito colateral:** não chama `ensure_channel_agents` e nunca faz chamadas externas ao YouTube (`avatar_url` usa apenas cache local se já aquecido; senão `null`).
- **Resposta `200 OK`:**
  ```json
  {
    "workspace_id": "uuid",
    "snapshot_at": "2026-11-17T17:15:00+00:00",
    "totals": { "channels": 1, "working": 2, "awaiting_human": 1, "problems": 0 },
    "channels": [
      {
        "channel": {
          "id": "uuid",
          "display_name": "O Outro Lado",
          "handle": "@outroladodetudo",
          "status": "active",
          "avatar_url": null,
          "niche": "Mistérios"
        },
        "provisioned": true,
        "agents": [
          { "agent_key": "dados", "room_key": "sala_dados", "status": "idle", "enabled": true, "progress": null }
        ],
        "counts": {
          "working": 0,
          "awaiting_human": 0,
          "blocked": 0,
          "failed": 0,
          "agents": 7,
          "disabled_agents": 1
        },
        "active_item": { "id": "uuid", "working_title": "Episódio", "stage": "roteiro" },
        "last_event_at": "2026-11-17T17:10:00+00:00"
      }
    ]
  }
  ```

---

## 3. Portas de Integração (`adapters/`)

1. **`YouTubeAdapter`**: `authorize_url()`, `exchange_code()`, `refresh_token()`, `fetch_channel_catalog()`, `fetch_video_statistics()`, `fetch_analytics_report()`, `search_public_channels_and_videos()`. Respeita `QuotaLedger` e retorna indisponibilidade explícita.
2. **`AIProviderRouter`**: `classify()`, `generate_structured()`, `embed_batch()`, `analyze_image_ocr()`. Recebe `workspace_id`, `role`, `consent_granted` para envio externo e `budget_limit`. Bloqueia fallback externo silencioso (`AI_EXTERNAL_CONSENT_REQUIRED` / `AI_PROVIDER_UNAVAILABLE`).
3. **`RAGRetriever`**: `retrieve_context(workspace_id, channel_id, query, allowed_levels=['L2','L3'], rights_filter, embedding_revision_id)`. Aplica filtro SQL/RLS antes de montar `ContextPack` e valida chunk IDs pós-consulta.
4. **`DarkForgeGateway`**: `submit_production_intent(ProductionIntent)`, `poll_status(intent_id)`, `request_pause(intent_id)`, `request_cancel(intent_id)`, `fetch_manifest(intent_id)`. Só aceita brief `APPROVED`; se o núcleo DarkForge estiver ausente (`SP-00-T02`), retorna `DARKFORGE_UNAVAILABLE` sem criar executor paralelo.
