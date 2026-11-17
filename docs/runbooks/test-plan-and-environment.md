# Ambiente e Plano de Testes (SP-00-T09)

**Data:** 2026-11-16  
**Referências:** [docs/execution/master-plan.md](../execution/master-plan.md) (§7, §8), [docs/execution/traceability.md](../execution/traceability.md) (§3)

---

## 1. Matriz de Ambiente Observada

| Componente | Estado atual | Requisito para validação real |
|---|---|---|
| Node.js / pnpm | `v22.17.0` / `12.6.0` | Pronto para `apps/web` |
| Python | `3.13.5` | Pronto para `apps/api`, `core/`, `workers/` (usar `.venv`) |
| Supabase Projeto | `https://pqtwhwjrpgxpagkyxktk.supabase.co` + Publishable Key + Legacy JWT Secret | Faltam `SUPABASE_SERVICE_ROLE_KEY` e `DATABASE_URL` (ou `supabase login` na conta proprietária) para migrations, `SKIP LOCKED`, RLS e Storage |
| Docker / Supabase Local | Docker `29.8.2` instalado, daemon parado | Opcional para testes locais se daemon for iniciado |
| Postgres CLI (`psql`/`pg_dump`) | Ausente no `PATH` | Instalar PostgreSQL Client ou usar Docker/script lógico para `SP-09` |
| Dois Usuários / Workspaces (`WS-A`, `WS-B`) | Planejados | Criar em `SP-01` via Supabase Auth (com `SUPABASE_SERVICE_ROLE_KEY`) antes de importar dados reais |
| Buckets Storage Privados | `knowledge`, `references`, `exports`, `production` | Criar e testar policies em `SP-02` |
| YouTube OAuth | Não configurado | Necessário apenas a partir de `SP-03` (`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`) |
| Provedor de IA | Hardware: 16 GB RAM, Intel HD 4600 (sem GPU dedicada) | Modelos leves locais ou API externa configurada explicitamente (`AI_EXTERNAL_CONSENT_REQUIRED`) |
| Núcleo DarkForge | Código-fonte ausente no workspace (`SP-00-T02`) | Necessário apenas em `SP-08`; até lá contratos permanecem isolados |

---

## 2. Estratégia de Testes Obrigatórios

1. **Unitários (`tests/unit/`):** regras de domínio, `OpportunityScore`, estado de métricas (`unknown` != `0`), state machines, idempotência, anti-cópia e redaction.
2. **Contratos (`tests/contracts/`):** validação contra schemas JSON em `contracts/` e invariantes de erro/SSE.
3. **Integração & RLS (`tests/integration/`):** `T-SEC-001` (2 usuários/workspaces cruzados em UI, API, RPC, pgvector e Storage), `T-SEC-002` (`security definer` + `search_path`).
4. **Fila, Storage & Recovery (`tests/integration/`):** `T-JOB-001` (disputa de 2 workers), `T-JOB-002` (lease expirado + fencing), `T-JOB-003` (crash pós-efeito externo), `T-JOB-004` (Supabase offline -> `BLOCKED`), `T-STO-001` (upload interrompido, checksum, manifest `READY`, órfãos).
5. **Avaliação IA/RAG (`tests/evaluation/`):** `T-RAG-001/002`, `T-AI-001` sobre os golden datasets em `tests/evaluation/datasets/`.
6. **Release & E2E (`tests/e2e/`):** `T-REL-001` (instalação limpa, upgrade, backup/restore completo Postgres + Storage) e `T-E2E-001` (21 passos do PRD).
