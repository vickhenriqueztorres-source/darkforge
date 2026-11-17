# UI-03 — API de estado do studio

**Objetivo:** entregar à interface um snapshot consistente por canal e um fluxo de eventos recuperável.  
**Depende de:** UI-01, UI-02.  
**Gate:** G-UI3.

## Tarefas

### UI-03-T01 — Snapshot do canal
Endpoint/loader no servidor `getStudioSnapshot(channelId)` que retorna: canal, salas (`v_studio_room_state`), agentes (`v_studio_agent_state`), content item ativo (`v_content_pipeline`), última oportunidade, métricas com frescor e o cursor do último evento.  
**Teste:** um único round-trip; respeita RLS; canal de outro workspace retorna 404.

### UI-03-T02 — Eventos por cursor
Endpoint `getStudioEvents(channelId, afterId, limit)` que lê `agent_events` em ordem.  
**Teste:** a paginação não perde nem duplica eventos.

### UI-03-T03 — Transporte em tempo real
Assinar inserções em `agent_events` do canal (Realtime ou equivalente existente). Ao receber, aplicar no estado local; se detectar lacuna de cursor, buscar pelo endpoint T02.  
**Teste:** derrubar a conexão, gerar eventos e reconectar reconstrói o estado idêntico ao snapshot.

### UI-03-T04 — Reducer de estado
Função pura `applyStudioEvent(state, event)` que deriva o status e a posição lógica dos agentes e o feed.  
**Teste:** testes unitários para cada `event_type`; eventos fora de ordem são ignorados por `seq`.

### UI-03-T05 — Frescor e estados de falha
Cada bloco do snapshot carrega `fetched_at` e `availability`. A UI recebe `stale` quando passar do limite configurado.  
**Teste:** métrica antiga vira `stale`; fonte indisponível vira `unknown`.

## Gate G-UI3
- [ ] Snapshot + replay reconstroem o estado após desconexão
- [ ] Reducer coberto por testes
- [ ] Nenhum vazamento entre workspaces
