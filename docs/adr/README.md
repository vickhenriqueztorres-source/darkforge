# Architecture Decision Records (ADRs) — DarkForge Channel OS

Índice dos ADRs obrigatórios definidos em [docs/architecture.md](../architecture.md) (§24) e exigidos por `SP-00-T03`.

| ADR | Título | Status | Subplanos |
|---|---|---|---|
| [ADR-001](ADR-001.md) | Web UI local como interface principal; EXE somente como launcher opcional | ACCEPTED | SP-01, SP-09 |
| [ADR-002](ADR-002.md) | Monólito modular Python e workers locais em vez de microserviços | ACCEPTED | SP-01, SP-02 |
| [ADR-003](ADR-003.md) | Command Bus e Job Manager únicos compartilhados com o DarkForge | ACCEPTED | SP-02, SP-08 |
| [ADR-004](ADR-004.md) | Supabase Postgres como fonte transacional única; sem segunda verdade SQLite | ACCEPTED | SP-01, SP-02, SP-08 |
| [ADR-005](ADR-005.md) | APIs oficiais primeiro e limites explícitos para dados públicos | ACCEPTED | SP-03, SP-04 |
| [ADR-006](ADR-006.md) | RAG com curadoria L0–L3 e proveniência, sem fine-tuning no MVP | ACCEPTED | SP-06 |
| [ADR-007](ADR-007.md) | Provider Router para IA local e externa sem fallback externo silencioso | ACCEPTED | SP-06, SP-07 |
| [ADR-008](ADR-008.md) | Aprovação humana obrigatória para brief e intenção de produção | ACCEPTED | SP-07, SP-08 |
| [ADR-009](ADR-009.md) | Versionamento imutável de perfil editorial, prompts, scores, fontes e embeddings | ACCEPTED | Todos |
| [ADR-010](ADR-010.md) | pgvector como projeção reconstruível com revisão e RLS | ACCEPTED | SP-06 |
| [ADR-011](ADR-011.md) | Supabase Auth, memberships e RLS como fronteira de autorização | ACCEPTED | SP-01 |
| [ADR-012](ADR-012.md) | Supabase Storage privado para binários; filesystem local só para temporários/cache | ACCEPTED | SP-02 |
| [ADR-013](ADR-013.md) | Fila Postgres com lease, fencing, outbox/inbox e idempotência | ACCEPTED | SP-02 |
| [ADR-014](ADR-014.md) | Estratégia de backup/PITR, Storage e restore testado com RPO/RTO explícitos | ACCEPTED | SP-09 |
| [ADR-015](ADR-015.md) | Comportamento em rede indisponível: modo degradado explícito sem falso sucesso | ACCEPTED | SP-02, SP-09 |
