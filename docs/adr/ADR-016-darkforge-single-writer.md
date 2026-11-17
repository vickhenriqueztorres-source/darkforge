# ADR-016 — Estratégia Single-Writer com o Núcleo DarkForge

- **Status:** Accepted (Bloqueio externo registrado para código-fonte DarkForge ausente)
- **Subplano:** SP-08 (`PROD-001`..`PROD-005`, `T-DF-001`)
- **Depende de:** ADR-003 (Command Bus e Job Manager compartilhados), ADR-004 (Supabase fonte única), ADR-008 (Aprovação humana), ADR-012 (Storage privado)

## 1. Contexto e Achado de Auditoria

A auditoria inicial (`docs/architecture/repo-and-darkforge-audit.md`) confirmou que o código-fonte do motor executor DarkForge (Command Bus/Job Manager/Scheduler/SQLite histórico) **não está presente** no repositório nem no ambiente local; apenas dois manifests históricos (`pipeline_version: media_vertical_v1`, com etapas `import_media`, `probe_media`, `render_media`, `validate_media`, `export_media`) existem em `C:\Users\brend\Documents\DarkForge`.

Conforme regra explícita de `SP-08`, é proibido inventar um executor paralelo de vídeo (`ffmpeg`) ou gerar mídia falsa.

## 2. Decisão Single-Writer

1. **Fonte única de estado:** `public.production_intents` + `public.jobs` + `public.artifacts` no Supabase Postgres são a única fonte de verdade (`ADR-004`). Nenhum SQLite local pode ser consultado pela UI ou pelas rotas `/api/v1` como verdade paralela.
2. **Gate humano obrigatório (`PROD-001` / `ADR-008`):** Nenhuma intenção de produção pode ser criada sem `episode_briefs.status = 'APPROVED'` e snapshot imutável (`brief_version`, `brief_content_sha256`, `idempotency_key`).
3. **Gateway desacoplado (`DarkForgeGatewayPort`):**
   - Quando `DARKFORGE_CORE_PATH` não estiver configurado/disponível, o gateway retorna `503 DARKFORGE_UNAVAILABLE` e mantém o job/intent em `BLOCKED` com erro acionável, sem fabricar `READY` ou arquivos falsos.
   - Quando `DARKFORGE_CORE_PATH` (ou driver real validado) estiver disponível, o executor recebe o snapshot congelado do brief via `CommandBus`, executa as etapas reais, faz upload para o bucket privado `production` com SHA-256 verificado, valida o `manifest.json` e somente então marca `manifest_validated = true` e `status = 'READY'` (`PROD-005`).
4. **Legado / Reconciliação (`PROD-004`):** Arquivos SQLite/manifest históricos só podem ser importados em modo read-only como manifests históricos ou reconciliados com `idempotent_effects`; nunca reabrem escrita paralela em SQLite.
