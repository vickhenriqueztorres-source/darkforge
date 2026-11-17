# Máquinas de Estado e Semântica Operacional (SP-00-T04)

**Data:** 2026-11-16  
**Referências:** [PRD](../prd.md), [Arquitetura](../architecture.md) (§7, §10, §12, §14), [ADR-004](../adr/ADR-004.md), [ADR-008](../adr/ADR-008.md), [ADR-012](../adr/ADR-012.md), [ADR-013](../adr/ADR-013.md), [ADR-015](../adr/ADR-015.md)

---

## 1. Semântica canônica de estados transversais

| Termo | Significado obrigatório | Proibição |
|---|---|---|
| `unknown` | Métrica ou atributo não retornado, não autorizado ou não suportado pela fonte no período | **Nunca** converter para `0` |
| `partial` | Operação ou lote obteve parte dos dados válidos e falhou em outra parte identificável | **Nunca** apagar dados válidos prévios nem rotular como `SUCCEEDED` completo |
| `delayed` | Fonte oficial indica janela de latência/processamento pendente | **Nunca** afirmar como valor definitivo |
| `not_applicable` | Dimensão ou métrica não existe para o formato/tipo (ex.: retenção para canal concorrente) | **Nunca** exibir `0` ou falha genérica |
| `blocked` | Dependência externa indisponível (rede, Supabase, quota, OAuth revogado, modelo ausente sem consentimento de fallback) | **Nunca** marcar sucesso nem falha definitiva irreversível quando recuperável |
| `interrupted` | Worker morreu/reiniciou ou lease expirou durante `RUNNING` | **Nunca** deixar preso em `RUNNING` nem duplicar efeitos ao retomar |
| `ready` | Objeto/artifact com upload concluído, checksum SHA-256 validado e manifest persistido no Postgres | **Nunca** atribuído antes da verificação completa |
| `LOCAL_COMPLETED_PENDING_SYNC` | Render/processamento local terminou, mas manifest/artifact ainda não foi confirmado no Supabase | **Nunca** tratado como `SUCCEEDED` global |

---

## 2. Job (`jobs.status`)

```text
QUEUED ──(claim + fencing)──▶ RUNNING
  ▲                              ├──▶ PAUSED ──(resume)──▶ QUEUED
  │                              ├──▶ CANCEL_REQUESTED ──(safe boundary)──▶ CANCELLED
  │                              ├──▶ BLOCKED ──(dep recovered)──▶ RECOVERABLE ──▶ QUEUED
  │                              ├──▶ INTERRUPTED ──(reconciler)──▶ RECOVERABLE ──▶ QUEUED
  │                              ├──▶ LOCAL_COMPLETED_PENDING_SYNC ──(manifest synced)──▶ SUCCEEDED
  │                              ├──▶ FAILED ──(retryable + backoff)──▶ QUEUED
  │                              └──▶ SUCCEEDED (somente após commit remoto + validação)
```

- **Regra de escrita:** toda transição exige validação de `fencing_token` (quando executada por worker) e grava `OutboxEvent` na mesma transação Postgres.
- **Cancelamento/Pausa:** UI registra `CANCEL_REQUESTED` / pedido de pausa; o estado final só muda quando o worker confirma em limite seguro.

---

## 3. Conexão OAuth e Sync (`platform_connections.status` e `sync_cursors.status`)

### 3.1 `PlatformConnection`
```text
PENDING_AUTH ──▶ CONNECTED ──▶ TOKEN_EXPIRED ──(refresh ok)──▶ CONNECTED
                    │                └──(refresh fail)──▶ REVOKED_OR_INVALID
                    └──(user disconnect / OAuth revoke)──▶ DISCONNECTED
```
- Revogar ou desconectar YouTube **não** encerra a sessão Supabase Auth do usuário (`AUTH-004`).

### 3.2 `SyncRun` / `MetricRevision`
```text
IDLE ──▶ SYNCING ──▶ SUCCEEDED (cursor + fatos commitados juntos)
            ├──▶ PARTIAL (parte das métricas/páginas ok; erro parcial registrado)
            ├──▶ BLOCKED (quota/rede/Supabase/OAuth)
            └──▶ FAILED
```
- Revisões de fatos métricos: `pending` -> `partial` -> `final` -> `revised` (mudança tardia cria revisão preservando histórico, `AN-007`).

---

## 4. Fonte de Conhecimento (`knowledge_sources.status` e níveis `L0`–`L3`)

```text
IMPORTED ──▶ NORMALIZED ──▶ DEDUPLICATED ──▶ REVIEWED ──▶ APPROVED ──▶ INDEXED
   │              │              │             │            │            │
   └──────────────┴──────────────┴─────────────┴────────────┴────────────┴──▶ REJECTED / ARCHIVED / DELETED
```

| Nível (`curation_level`) | Significado | Entra por padrão no RAG? |
|---|---|---|
| `L0` | Bruto, recém-importado, não revisado | **Não** |
| `L1` | Revisado (estrutura/origem conferidas) | Somente quando explicitamente filtrado |
| `L2` | Aprovado (copy/conhecimento autorizado) | **Sim** |
| `L3` | Canônico (referência principal do canal/marca) | **Sim, com prioridade** |

- `ARCHIVED` e `DELETED` são imediatamente excluídos de novas buscas (`KNOW-004`, `KNOW-007`) e invalidam caches de retrieval.

---

## 5. EmbeddingRevision (`embedding_revisions.status`)

```text
BUILDING ──▶ VALIDATING ──▶ ACTIVE ──▶ DEPRECATED ──▶ RETIRED
                └──▶ FAILED_VALIDATION (não substitui revisão ativa)
```
- Vetores de revisões distintas nunca são comparados na mesma consulta (`ADR-010`).

---

## 6. Oportunidade (`opportunities.status`)

```text
DRAFT ──▶ REVIEW ──▶ APPROVED ──▶ PLANNED ──▶ IN_PRODUCTION ──▶ PUBLISHED
             │          │                                           │
             ├──▶ REJECTED (preserva motivo, autor, data) ──────────┴──▶ ARCHIVED
             └──▶ ARCHIVED
```
- `IN_PROGRESS` / `IN_PRODUCTION` só ocorre após brief aprovado e intenção explícita (`SP-07`/`SP-08`).

---

## 7. Brief Editorial (`episode_briefs.status` + `version`)

```text
DRAFT ──▶ IN_REVIEW ──▶ APPROVED (versão congelada/imutável) ──▶ SUPERSEDED (quando nova versão v+1 é criada)
                          └──▶ ARCHIVED
```
- **Invariante (`EDIT-003`, `ADR-008`):** editar um brief `APPROVED` nunca sobrescreve a versão congelada; cria `version + 1` em `DRAFT`. Somente `APPROVED` pode gerar `ProductionIntent`.

---

## 8. StorageObject e Artifact (`storage_objects.status` / `artifacts.status`)

```text
UPLOADING ──▶ VERIFYING (sha256 + tamanho + manifest) ──▶ READY
    │              └──▶ FAILED / ORPHANED (elegível para reconciler/limpeza)
    └──▶ FAILED / ORPHANED
```
- Nenhum artifact de produção ou export aparece como concluído antes de `READY`.
