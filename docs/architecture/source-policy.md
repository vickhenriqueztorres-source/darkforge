# Política de Fontes, Retenção, Direitos e Privacidade (SP-00-T05)

**Data:** 2026-11-16  
**Referências:** `CH-005`..`CH-008`, `RES-001`..`RES-007`, `KNOW-001`..`KNOW-007`, [ADR-005](../adr/ADR-005.md), [ADR-006](../adr/ADR-006.md), [ADR-007](../adr/ADR-007.md)

---

## 1. Classificação de Fontes

| Classe | Origem | Uso permitido | Proibições |
|---|---|---|---|
| **Próprias autorizadas** | YouTube Data/Analytics/Reporting API via OAuth | Dashboards privados, histórico, diagnósticos, perfilamento interno | Vazamento para outros workspaces; envio a IA externa sem consentimento |
| **Públicas de referência** | YouTube Data API pública / URL oficial informada pelo usuário | Pesquisa de mercado, similaridade observável, análise estrutural de títulos/capas | Scraping abusivo, bypass de auth/robots, inferência de métricas privadas, cópia literal |
| **Conhecimento curado** | Copies, roteiros, guias importados pelo usuário (`L0`–`L3`) | Indexação FTS + pgvector e contexto RAG (conforme nível `L0–L3` e direitos) | Tratamento como instrução de sistema (`prompt injection`); uso após arquivamento/exclusão |

---

## 2. Escopos OAuth Mínimos (YouTube)
- Leitura de catálogo próprio: `https://www.googleapis.com/auth/youtube.readonly`
- Leitura de analytics próprio: `https://www.googleapis.com/auth/yt-analytics.readonly`
- **Sem escopo de escrita/publicação no MVP:** `youtube.upload` e `youtube.force-ssl` ficam fora do MVP (publicação automática é proibida).

---

## 3. Retenção e Exclusão

| Dado | Local | Retenção padrão | Comportamento na revogação/exclusão |
|---|---|---|---|
| Tokens OAuth (criptografados) | Supabase Postgres (cofre/referência) | Enquanto conexão ativa | Apagados imediatamente na desconexão/revogação |
| Métricas e catálogo de canal próprio | Supabase Postgres | Configurável (padrão: histórico editorial preservado se usuário optar, ou purge completo) | UI exige escolha explícita na desconexão (`CH-008`): manter histórico read-only ou excluir dados sincronizados |
| Raw JSON payloads de sync/pesquisa | Supabase Storage privado (`references`/`exports`) | 90 dias (comprimido, configurável) | Limpeza periódica pelo reconciler/política de retenção |
| Thumbnails públicas de referência | Referência + snapshot hash (Storage privado apenas se política permitir) | 30 dias para cache de análise | Não redistribuídas nem promovidas a asset publicável sem direitos |
| Fontes de conhecimento (`KnowledgeSource`) | Postgres + Storage + pgvector | Enquanto ativas | Exclusão remove `KnowledgeSource`, `KnowledgeChunk`, embeddings, objetos no Storage e invalida caches; UI informa sobre retenção eventual em backups |
| Logs de diagnóstico local | `%LOCALAPPDATA%\DarkForge\logs` | 14 dias | Redaction obrigatório de tokens, cookies, chaves e copies completas |

---

## 4. Direitos de Uso e Proveniência
- Todo `KnowledgeSource` registra `origin_type`, `rights_status` (`owned`, `licensed`, `internal_reference`, `restricted`), `allowed_in_generation` (boolean) e `curation_level` (`L0`–`L3`).
- `restricted` nunca pode ser usado em gerações de copy sem revisão explícita; `L0` nunca entra por padrão.
- Toda geração de IA externa exige exibição prévia das categorias de dados enviadas e consentimento explícito registrado no workspace (`ADR-007`).
