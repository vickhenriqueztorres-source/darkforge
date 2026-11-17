# Glossário Formal e Catálogo Canônico de Erros (SP-00-T04)

**Data:** 2026-11-16

---

## 1. Glossário Operacional

| Termo | Definição normativa |
|---|---|
| **Workspace** | Fronteira lógica de isolamento multi-tenant (`workspace_id`). Todas as tabelas, buscas e buckets exigem membership válido. |
| **Channel** | Identidade interna de um canal gerenciado dentro de um workspace. Um workspace suporta múltiplos canais. |
| **ChannelProfileVersion** | Snapshot versionado da identidade editorial (público, voz, pilares, formatos, temas proibidos, tema visual/editorial). |
| **PlatformConnection** | Autorização OAuth de um canal próprio no YouTube; distinta da sessão Supabase Auth. |
| **MetricSnapshot / MetricSeriesPoint** | Fato métrico normalizado com `source`, `period`, `granularity`, `dimensions_hash`, `availability` e `source_revision`. |
| **ResearchRun** | Execução auditável de pesquisa pública com objetivo, filtros, orçamento de quota e versão de algoritmo. |
| **ReferenceChannel / ReferenceVideo** | Entidade pública descoberta ou curada para análise comparativa; nunca carrega métricas privadas simuladas. |
| **KnowledgeSource / KnowledgeChunk** | Fonte editorial importada (copy, roteiro, guia) com direitos/licença, nível `L0–L3` e segmentos rastreáveis. |
| **EmbeddingRevision** | Conjunto isolado de vetores vinculados a um único `embedding_model`, `embedding_version` e `dimensions`. |
| **Opportunity** | Hipótese de episódio/tema com componentes de score, confiança, limitações e `EvidenceLink`s. |
| **EpisodeBrief** | Documento editorial versionado que consolida objetivo, ângulo, títulos, estrutura, CTA e fontes; imutável após aprovação. |
| **ProductionIntent** | Intenção idempotente gerada exclusivamente a partir de um `EpisodeBrief` aprovado para o gateway DarkForge. |
| **Artifact** | Output validado (ex.: vídeo final, relatório de qualidade, pacote de exportação) com `StorageObject` `READY` e checksum SHA-256. |
| **Falso sucesso** | Qualquer estado concluído sem persistência confirmada no Postgres e manifest/validação verificados. |

---

## 2. Formato Padrão de Erro da API (`/api/v1`)

Conforme [docs/architecture.md](../architecture.md) §11.1:

```json
{
  "code": "STRING_ENUM",
  "message": "Mensagem clara para o operador, sem vazar segredos.",
  "retryable": false,
  "details": {
    "next_action": "Ação recomendada ao usuário"
  },
  "correlation_id": "uuid",
  "job_id": "uuid-ou-null"
}
```

---

## 3. Catálogo de Códigos de Erro

| Código | HTTP | `retryable` | Causa | Estado UI / Próxima ação |
|---|---|---|---|---|
| `AUTH_UNAUTHENTICATED` | 401 | false | Sessão ausente ou JWT expirado | Redirecionar para login Supabase |
| `WORKSPACE_FORBIDDEN` | 403 | false | Usuário sem membership ou ID de outro workspace | Estado `Sem permissão` (nunca mostrar vazio) |
| `RESOURCE_NOT_FOUND` | 404 | false | Recurso inexistente no escopo do workspace | Estado `Não encontrado` |
| `VALIDATION_ERROR` | 422 | false | Payload inválido ou campo obrigatório ausente | Destacar campo com instrução |
| `IDEMPOTENCY_CONFLICT` | 409 | false | Mesma `Idempotency-Key` com payload divergente | Informar conflito e gerar nova chave se intencional |
| `VERSION_CONFLICT` | 409 | true | Optimistic locking (`version` desatualizada) ou brief já aprovado | Recarregar versão atual ou criar `v+1` |
| `SUPABASE_UNAVAILABLE` | 503 | true | Rede offline, timeout ou projeto Supabase pausado/inacessível | Banner degradado + `BLOCKED`; bloquear escrita/conclusão |
| `OAUTH_REQUIRED_OR_REVOKED` | 401 | false | Conexão YouTube expirada/revogada | Exibir estado da conexão e botão `Reconectar YouTube` |
| `YOUTUBE_QUOTA_EXCEEDED` | 429 | true | Orçamento no `QuotaLedger` esgotado | `BLOCKED` recuperável; priorizar sync próprio |
| `AI_PROVIDER_UNAVAILABLE` | 503 | true | Modelo local offline ou timeout; fallback externo bloqueado | `BLOCKED` recuperável; solicitar consentimento explícito se desejar provedor externo |
| `AI_EXTERNAL_CONSENT_REQUIRED` | 412 | false | Política exige confirmação do usuário antes de envio externo | Mostrar categorias de dados e solicitar aprovação |
| `AI_BUDGET_EXCEEDED` | 429 | false | Limite de custo/tokens do job ou workspace atingido | Revisar orçamento antes de reexecutar |
| `ORIGINALITY_SIMILARITY_BLOCKED` | 422 | false | Similaridade excessiva com referência pública (`ORIG-001`) | Revisar e diferenciar antes de aprovar |
| `STORAGE_CHECKSUM_MISMATCH` | 422 | true | SHA-256 ou tamanho divergente após upload | Marcar objeto `FAILED/ORPHANED` e repetir upload |
| `FENCING_TOKEN_STALE` | 409 | false | Worker zumbi tentou gravar com token antigo | Abortar escrita local do worker antigo |
| `DARKFORGE_UNAVAILABLE` | 503 | true | Núcleo DarkForge não localizado/indisponível | Manter brief exportável; marcar produção `BLOCKED` |
