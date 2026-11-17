# Como adicionar um novo agente no DarkForge Studio UI

Guia objetivo para estender a equipe de agentes de cada canal mantendo rastreabilidade, validação de contrato e isolamento RLS.

## 1. Catálogo no banco (`migrations/`)
1. Crie uma nova migration SQL (`migrations/0018_...sql`).
2. Se precisar de nova sala, insira em `public.studio_rooms`.
3. Insira o agente em `public.agent_definitions` (`key`, `display_name`, `room_key`, `description`, `output_types`, `requires_approval`, `contract_version = 1`, `active = true`).
4. Faça backfill idempotente em `public.channel_agents` com `ON CONFLICT (channel_id, agent_key) DO NOTHING`. O trigger `app.seed_channel_agents_for_channel()` já lê `public.agent_definitions WHERE active = true` automaticamente para novos canais.

## 2. Contrato de saída (`core/studio/contracts.py`)
1. Crie o modelo Pydantic herdando de `StrictContractModel` (`extra="forbid"`).
2. Registre o `output_type` no dicionário `PAYLOAD_MODELS` e adicione a `key` ao literal `AgentKey`.
3. Garanta que campos ausentes ou métricas indisponíveis nunca virem `0` (use `null` + `availability`).

## 3. Registro de execução (`core/studio/registry.py`)
1. Adicione uma entrada em `AGENT_REGISTRY` definindo `room_key`, `output_type`, `requires_approval`, `responsibility`, `payload_model`, `depends_on_agents` e `next_agents`.
2. Insira a `key` na posição correta de `PIPELINE_ORDER`.
3. Rode `tests/unit/test_studio_contracts_and_registry.py` para confirmar paridade entre registro e contratos.

## 4. Gerador/Worker (`workers/agents/handler.py`)
1. Adicione o carregamento de entradas autorizadas em `PostgresStudioRepository.load_authorized_context()` (sempre filtrando por `workspace_id` e `channel_id`).
2. Implemente o caminho determinístico local em `default_local_agent_model_caller()` ou integre ao `AIProviderRouter`.

## 5. Cena e Layout (`apps/web/src/lib/studio/`)
1. Adicione a `key` em `AgentKey` (`types.ts`) e um avatar em `AGENT_AVATARS` (`StudioStage.tsx`).
2. Confirme em `STUDIO_LAYOUT` (`studio-layout.ts`) que a sala escolhida tem um `desk` livre em `desks[]` para o novo agente.
3. Rode `pnpm --filter @darkforge/web test:studio` e `pnpm typecheck:web`.
