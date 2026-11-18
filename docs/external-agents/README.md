# Integração do Projeto Separado (`O Outro Lado`) ao Agente Central (`YOUTUBE MANAGET`)

## 1. Arquitetura do Banco de Dados (Supabase Postgres — Migration `0019`)

- **`public.external_agent_catalog`**: Catálogo completo dos **88 agentes, bots, subagentes e gates** (`standalone`, `hsl_editorial`, `hsl_cinematic`, `hsl_media`, `hsl_postprod`, `shorts_cutter`), mapeando cada um para a sala 3D correspondente (`sala_dados`, `pesquisa`, `mesa_agentes`, `gravacao`, `design_thumbnail`, `estrategia_publicacao`).
- **`public.external_pipeline_runs`**: Agrupa execuções por episódio HSL, batch do Shorts Cutter, fila Firefly ou bots standalone.
- **`public.external_agent_executions`**: Estado exato de cada agente (`queued`, `working`, `waiting_input`, `waiting_approval`, `blocked`, `done`, `gate_passed`, `gate_failed`, `failed`, `no_signal`), etapa atual (`stage_label`), `progress`, `model_name`, `duration_ms`, `metrics`, `artifacts` e `error_message`.
- **`public.external_agent_events`**: Feed append-only publicado no `supabase_realtime` para atualização instantânea na UI.
- **`public.external_ingest_tokens`**: Tokens `df_ext_...` escopados por workspace/canal (armazenados com hash SHA-256) para o projeto separado autenticar na API central sem expor `SUPABASE_SERVICE_ROLE_KEY`.
- **`public.ingest_external_agent_event(...)`**: RPC atômica que cria/atualiza o pipeline run, registra a execução, calcula `duration_ms` e emite evento Realtime.
- **Views (`security_invoker = true`)**: `v_external_agent_latest_state`, `v_external_room_rollup`, `v_external_pipeline_summary`.

## 2. Como conectar o projeto separado

### Opção A — Via API HTTP Central (recomendado)
1. No painel do canal (`Estúdio do canal` → `Central de Agentes Externos`), clique em **Conectar projeto separado (Token & SDK)** e gere um `X-Ingest-Token`.
2. Copie [telemetry_client.py](telemetry_client.py) (para Python) ou [telemetryClient.ts](telemetryClient.ts) (para TypeScript) para o outro repositório.
3. Configure no `.env` do outro projeto:
   ```env
   MANAGET_API_URL=http://127.0.0.1:8000
   MANAGET_INGEST_TOKEN=df_ext_...
   MANAGET_CHANNEL_ID=<UUID_DO_CANAL>
   ```

### Opção B — Direto no Supabase (sem passar pela API local)
Configure no `.env` do outro projeto:
```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>
MANAGET_WORKSPACE_ID=<UUID_DO_WORKSPACE>
MANAGET_CHANNEL_ID=<UUID_DO_CANAL>
```
Os mesmos helpers [telemetry_client.py](telemetry_client.py) e [telemetryClient.ts](telemetryClient.ts) detectam automaticamente `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` quando `MANAGET_INGEST_TOKEN` não estiver definido e chamam `/rest/v1/rpc/ingest_external_agent_event`.

## 3. Exemplo rápido (Python — Shorts Cutter / Firefly)

```python
from telemetry_client import CentralTelemetryClient

telemetry = CentralTelemetryClient()

with telemetry.track_agent(
    agent_key="agent_04_moment_miner",
    external_run_id="shorts-ep-42",
    pipeline_kind="shorts_cutter",
    run_title="Cortes EP #42 - O Outro Lado",
    stage_label="Minerando candidatos nos 7 tipos...",
    model_name="claude-sonnet-4-6",
) as ctx:
    # sua logica aqui...
    ctx["metrics"] = {"candidates_found": 11}
```

## 4. Exemplo rápido (TypeScript — Pipeline HSL / Sound Agent)

```ts
import { CentralTelemetryClient } from "./telemetryClient";

const telemetry = new CentralTelemetryClient();

await telemetry.track(
  {
    agentKey: "NarrationVoiceAgent",
    externalRunId: "ep-42-hsl",
    pipelineKind: "hsl_episode",
    runTitle: "Episódio #42",
    stageLabel: "Sintetizando voz ElevenLabs Chris (-16 LUFS)",
    modelName: "ElevenLabs Chris",
  },
  async () => {
    // execucao do agente...
  }
);
```
