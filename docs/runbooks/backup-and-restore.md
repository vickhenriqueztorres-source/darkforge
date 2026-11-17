# Runbook de Backup, Restore Isolado & Diagnóstico Seguro (`ADR-014`, `JOB-007`, `JOB-008`)

## 1. Objetivos RPO / RTO

- **RPO alvo:** <= 24h via backup lógico agendado (`scripts/backup/backup_and_restore.py`) + PITR gerenciado do Supabase em produção.
- **RTO alvo:** <= 60 minutos para restore lógico isolado de um workspace completo (dados relacionais + blobs no Storage privado com verificação SHA-256).

## 2. Backup Lógico + Storage (`JOB-008`)

Como `psql`/`pg_dump` não estão instalados nativamente no PATH Windows atual, o script `scripts/backup/backup_and_restore.py` executa snapshot consistente via `psycopg` em transação `REPEATABLE READ READ ONLY` e exporta objetos `READY` do Supabase Storage validando SHA-256 bit a bit:

- Gera `manifest.json` (contagens e checksums SHA-256)
- Gera `tables.json` (workspaces, members, channels, profiles, opportunities, briefs, calendar, knowledge metadata, storage metadata)
- Grava binários verificados em `storage_files/`

Quando Docker / `pg_dump` estiverem disponíveis em produção, complementar com:
`pg_dump "$DATABASE_URL" --format=custom --schema=public --schema=app -f backup.dump`

## 3. Restore Isolado e Verificação (`T-REL-001`)

`restore_workspace_isolated(...)`:
1. Nunca sobrescreve o workspace de origem.
2. Cria um novo `workspace_id` isolado com membro `owner`.
3. Remapeia `channel_id`, `profile_version_id`, `opportunity_id`, `brief_id`, mantendo versões, estado `APPROVED` congelado e `content_sha256` intactos.
4. Valida SHA-256 de cada arquivo em `storage_files/`, faz upload sob prefixo `{new_workspace_id}/restored/...` e registra `storage_objects` como `READY`.

## 4. Pacote de Diagnóstico com Redaction (`JOB-007`)

Endpoint: `GET /api/v1/diagnostics/export` (`scripts/diagnostics/export_diagnostics.py`)
- Redige automaticamente padrões `Bearer ...`, JWTs `eyJ...`, `sb_secret_...` e senhas em URLs Postgres.
- Exclui `platform_connection_secrets`, `oauth_states` e `knowledge_sources.content_text`.
