# Auditoria do Repositório e do Núcleo DarkForge (SP-00-T01 / SP-00-T02)

**Data:** 2026-11-16  
**Workspace:** `d:\YOUTUBE MANAGET`  
**Status:** `SP-00-T01` DONE | `SP-00-T02` BLOCKED (código-fonte do núcleo DarkForge ausente no repositório; inventário baseado apenas em artefatos reais observados)

---

## 1. Mapa do Repositório e Ambiente (SP-00-T01)

### 1.1 Estado inicial do repositório
- `d:\YOUTUBE MANAGET` iniciou vazio (`0` arquivos) e recebeu a cópia integral de `README.md` e `docs/` de `darkforge-docs-completo` (hashes SHA-256 idênticos aos anexos de entrada).
- Não existem `AGENTS.md`, `package.json`, `pyproject.toml`, `migrations/` ou testes prévios no workspace.
- Estrutura alvo adotada conforme `docs/architecture.md` §13:
  - `apps/web/` — Next.js / React / TypeScript (Web UI local)
  - `apps/api/` — Python / FastAPI (BFF local, rotas `/api/v1`, SSE com replay)
  - `core/` — Domínio e Application Services (`channels`, `analytics`, `research`, `opportunities`, `knowledge`, `generation`, `editorial`, `darkforge_gateway`, `jobs`)
  - `workers/` — Workers locais Python (`sync`, `research`, `indexing`, `production`, `reconciler`)
  - `adapters/` — Fronteiras externas (`youtube`, `ai_providers`, `vision_ocr`, `supabase_db`, `supabase_storage`, `supabase_auth`)
  - `contracts/` — Schemas versionados de API, eventos e comandos (`api/`, `events/`, `schemas/`)
  - `prompts/` — Templates versionados (`analysts/`, `generation/`, `evaluation/`)
  - `migrations/` — Migrations SQL Postgres, RLS, grants e RPCs
  - `tests/` — `unit/`, `integration/`, `contracts/`, `evaluation/`, `e2e/`
  - `docs/` — PRD, arquitetura, ADRs, contratos, métricas, runbooks, execução
  - `scripts/` — `backup/`, `diagnostics/`, `packaging/`

### 1.2 Toolchain e hardware observados
| Recurso | Versão / Valor observado | Impacto arquitetural |
|---|---|---|
| OS | Windows | Paths e scripts compatíveis com Windows / PowerShell |
| Node.js | `v22.17.0` | Suporta Next.js moderno |
| pnpm | `12.6.0` | Gerenciador de pacotes para `apps/web` e schemas TS |
| Python | `3.13.5` | Runtime para `apps/api`, `core/`, `workers/` |
| Git | `2.50.1.windows.1` | Versionamento local (sem push remoto sem autorização) |
| Supabase CLI | `2.48.3` | Autenticado em org diferente (`kmlukndupueficakehzt`), não vinculado a `pqtwhwjrpgxpagkyxktk` |
| Docker | `29.8.2` (daemon parado) | Sem stack local ativa no momento |
| FFmpeg / FFprobe | `8.1` (`gyan.dev`) | Disponível no host para o futuro pipeline de produção (nunca chamado pela UI) |
| `psql` / `pg_dump` | Ausentes no `PATH` | Requer cliente Postgres ou container Docker quando executar `SP-09` restore |
| RAM / GPU | ~16 GB RAM (`17,097,854,976` bytes), `Intel(R) HD Graphics 4600` (1 GB) | Sem GPU dedicada; modelos locais pesados de LLM/visão são limitados a CPU/modelos pequenos ou provedor externo explícito com consentimento |

---

## 2. Auditoria do Núcleo DarkForge (SP-00-T02)

### 2.1 Evidências reais encontradas no disco
- **Código-fonte do núcleo DarkForge:** **NÃO ENCONTRADO** em `d:\YOUTUBE MANAGET` nem nas pastas inspecionadas de `D:\` e `C:\Users\brend\Documents`.
  - `D:\edition pro\voicecut` e `D:\forge edition\voicecut` pertencem a um pipeline distinto (`VoiceCut`: TTS -> VAD -> MUX -> SFX com `voicecut.db`).
- **Artefatos de execução DarkForge observados:** `C:\Users\brend\Documents\DarkForge\` contém 2 diretórios de jobs executados em `2026-08-19`:
  - `job_57d79b575be4478bab9f5ed69940555a`
  - `job_816b12ab19664ef0933b08336e100c0b`
- Estrutura observada em `C:\Users\brend\Documents\DarkForge\job_57d79b575be4478bab9f5ed69940555a\manifest.json`:
  - `pipeline_version`: `"media_vertical_v1"`
  - `pipeline_fingerprint` / `config_fingerprint`: SHA-256 hex (64 chars)
  - `status`: `"COMPLETED"`
  - `steps` executados sequencialmente:
    1. `import_media` (`SOURCE_MEDIA`, `source/input.mp4`, `sha256`, `size_bytes`, `validated: true`)
    2. `probe_media` (`MEDIA_METADATA`, `artifacts/media-info.json`)
    3. `render_media` (gera `intermediate/rendered.mp4.partial`)
    4. `validate_media` (`MEDIA_VALIDATION`, `artifacts/media-validation.json`, checks de container `mp4`, `duration_positive`, `duration_match`, `video_stream`, `h264`, `resolution`, `fps`, `yuv420p`, `audio_presence`, `aac`, `decode_sanity`)
    5. `export_media` (`FINAL_VIDEO`, `outputs/final_<job_id>.mp4`, `sha256`, `validated: true`)
  - Subdiretórios por job: `artifacts/`, `diagnostics/` (`*_ffprobe.process.json`, `*_ffmpeg.process.json`), `intermediate/`, `outputs/`, `source/`, `manifest.json`.

### 2.2 Respostas às 8 perguntas obrigatórias do SP-00 §3

| Pergunta | Resposta auditada (sem suposição) | Estado |
|---|---|---|
| 1. O Job Manager existente pode persistir no Supabase ou será substituído por um manager único? | Código-fonte do Job Manager DarkForge não está disponível no workspace. Portanto, o Channel OS implementará o **Job Manager único no Supabase Postgres** (`jobs`, `job_attempts`, `job_leases`, `job_events`, `outbox_events`) conforme `ADR-003`/`ADR-004`/`ADR-013`, e o futuro executor DarkForge receberá intenções idempotentes via `DarkForgeGateway` (`SP-08`). | DECIDIDO / CONDICIONADO |
| 2. Quem é o escritor de cada entidade hoje? | Repositório é greenfield: o Channel OS (via Postgres/workers) é o **single-writer** de workspaces, canais, métricas, pesquisas, conhecimento, oportunidades, briefs e jobs. O executor DarkForge (quando conectado em `SP-08`) será single-writer apenas de seus steps internos e `manifest.json` local antes da promoção para Storage/`ready` no Supabase. | DEFINIDO |
| 3. O executor aceita comandos idempotentes e informa progresso real? | **Não comprovável sem o código-fonte do executor.** O `manifest.json` observado registra `steps` discretos (`import_media`, `probe_media`, `render_media`, `validate_media`, `export_media`) e `input_fingerprint`, mas a API Python/CLI de comando, idempotência e streaming de progresso não estão presentes. Bloqueio registrado para `SP-08`. | BLOCKED (código ausente) |
| 4. Como pause/resume/cancel funcionam de fato? | **Não comprovável sem o código-fonte do executor.** O Channel OS implementará pause/resume/cancel em checkpoints seguros na sua própria fila Postgres (`SP-02`); o repasse ao executor DarkForge fica condicionado à revalidação em `SP-08-T01`. | BLOCKED (código ausente) |
| 5. O que é artifact válido e onde seu manifest é gravado? | Nos artefatos observados em `Documents\DarkForge`, um output válido possui `manifest.json` na raiz do job com `artifacts[]` (`artifact_id`, `artifact_type`, `path`, `sha256`, `size_bytes`, `step_id`, `validated: true`) e checks de `media-validation.json` todos `passed: true`. No Channel OS, o manifest e os binários finais só atingem `ready` após upload verificado no Supabase Storage privado e commit em `artifacts` + `storage_objects`. | PARCIALMENTE OBSERVADO |
| 6. Quais métricas o YouTube realmente disponibiliza para os canais de teste? | Canal de teste e credenciais OAuth ainda não foram fornecidos/conectados. Catálogo de métricas (`SP-00-T05`) separa explicitamente métricas privadas autorizadas (YouTube Analytics API) de snapshots públicos (YouTube Data API) e impõe estado `unknown` quando indisponível. | PENDING (credenciais OAuth em `SP-03`) |
| 7. Quais dados podem ser retidos e por quanto tempo? | Política de fontes definida em `docs/architecture/source-policy.md` (`SP-00-T05`): raw payloads e thumbnails públicas têm TTL configurável, revogação OAuth preserva histórico editorial próprio apenas se autorizado ou executa exclusão explícita, e copies de conhecimento seguem licença/direitos registrados. | DEFINIDO |
| 8. Quais modelos de IA/visão cabem no hardware previsto? | Host possui 16 GB RAM e GPU integrada Intel HD 4600 (1 GB VRAM, sem CUDA). Modelos locais viáveis ficam restritos a CPU/modelos compactos (ex.: embeddings pequenos 384d–768d ou SLM quantizado 3B–7B em RAM) com baixa concorrência; visão/OCR ou geração pesada exigem provedor externo configurado explicitamente com consentimento (`ADR-007`). | VERIFICADO |
