# Catálogo de Métricas (SP-00-T05)

**Data:** 2026-11-16  
**Referências:** `AN-001`..`AN-007`, `RES-006`, [docs/architecture.md](../architecture.md) §8, [ADR-005](../adr/ADR-005.md)

---

## 1. Regras Globais de Métricas

1. **Ausência não é zero (`AN-004`):** valores não retornados ou não elegíveis têm `availability` em `unknown | delayed | partial | not_applicable` e `value: null`.
2. **Proveniência obrigatória (`AN-005`):** toda métrica persiste `source`, `source_revision`, `period_start`, `period_end`, `granularity`, `dimensions_hash`, `is_estimate`, `fetched_at`.
3. **Separação Público vs. Privado (`RES-006`):** métricas com `visibility_scope = 'private_authorized'` nunca existem para `ReferenceChannel`/`ReferenceVideo`.
4. **Compatibilidade de comparação (`AN-006`):** comparações entre vídeos/canais só ocorrem quando `metric_id`, `granularity`, `dimensions_schema_version` e janela temporal são compatíveis; caso contrário a API/UI bloqueia ou sinaliza incompatibilidade.
5. **Preservação de revisões (`AN-007`):** dados tardios ou corrigidos pela API oficial gravam nova `source_revision` sem apagar o registro anterior.

---

## 2. Catálogo Versionado (`catalog_version = "v1"`)

| `metric_id` | Nome | Escopo | Fonte oficial | Granularidades | Dimensões válidas | Comportamento se ausente/atrasada |
|---|---|---|---|---|---|---|
| `yt.channel.subscribers_total` | Inscritos totais | `private_authorized` ou `public_snapshot` (quando visível) | Data API `channels.statistics` | `snapshot` | `{}` | Se `hiddenSubscriberCount=true`, marcar `not_applicable` / `unknown` (nunca `0`) |
| `yt.video.public_views` | Visualizações públicas (snapshot) | `public_snapshot` e `private_authorized` | Data API `videos.statistics` | `snapshot` | `{}` | `unknown` se API falhar; guardar timestamp do snapshot |
| `yt.video.public_likes` | Likes públicos (snapshot) | `public_snapshot` e `private_authorized` | Data API `videos.statistics` | `snapshot` | `{}` | `unknown` se oculto pelo criador ou indisponível |
| `yt.video.public_comments` | Comentários públicos (snapshot) | `public_snapshot` e `private_authorized` | Data API `videos.statistics` | `snapshot` | `{}` | `unknown` se comentários desativados ou falha |
| `yt.analytics.views` | Views consolidadas (Analytics) | `private_authorized` apenas | Analytics API (`views`) | `day`, `period_total` | `{}`, `{country}`, `{traffic_source}` | `delayed` nas últimas 48–72h; `unknown` se sem escopo `yt-analytics.readonly` |
| `yt.analytics.watch_time_minutes` | Tempo de exibição (min) | `private_authorized` apenas | Analytics API (`estimatedMinutesWatched`) | `day`, `period_total` | `{}`, `{country}`, `{traffic_source}` | `delayed` ou `unknown`; nunca `0` por falta de escopo |
| `yt.analytics.avg_view_duration_sec` | Duração média da visualização (s) | `private_authorized` apenas | Analytics API (`averageViewDuration`) | `day`, `period_total` | `{}` | `unknown` quando `views` indisponível ou sem escopo |
| `yt.analytics.avg_view_percentage` | Percentual médio assistido | `private_authorized` apenas | Analytics API (`averageViewPercentage`) | `day`, `period_total` | `{}` | `unknown` se vídeo curto/sem dados suficientes |
| `yt.analytics.subscribers_gained` | Inscritos ganhos | `private_authorized` apenas | Analytics API (`subscribersGained`) | `day`, `period_total` | `{}` | `delayed` / `unknown` |
| `yt.analytics.subscribers_lost` | Inscritos perdidos | `private_authorized` apenas | Analytics API (`subscribersLost`) | `day`, `period_total` | `{}` | `delayed` / `unknown` |
| `yt.analytics.impressions` | Impressões de miniatura | `private_authorized` apenas | Analytics / Reporting API | `day`, `period_total` | `{}` | Frequente indisponibilidade na API padrão; marcar `unknown` ou `not_applicable` |
| `yt.analytics.impressions_ctr` | CTR de impressões (%) | `private_authorized` apenas | Analytics / Reporting API | `day`, `period_total` | `{}` | **Proibido** estimar para concorrentes; `unknown` se não retornado |
| `yt.analytics.retention_curve` | Curva de retenção de audiência | `private_authorized` apenas | Analytics API (`audienceWatchRatio` via `elapsedVideoTimeRatio`) | `curve_100` | `{audience_type}` | `unknown` quando volume mínimo não atingido ou sem elegibilidade |
| `yt.analytics.traffic_sources` | Fontes de tráfego | `private_authorized` apenas | Analytics API (`insightTrafficSourceType`) | `period_total` | `{traffic_source_type}` | Não combinar `traffic_source_type` com `country` sem confirmar suporte da API |

---

## 3. Regras de Incompatibilidade de Comparação (`AN-006`)
- Proibido somar ou comparar diretamente `yt.video.public_views` (snapshot acumulado) com `yt.analytics.views` (série diária de janela parcial) sem conversão/rotulagem explícita.
- Proibido comparar `period_total` com `day` na mesma série sem agregação compatível.
- Proibido exibir métricas `delayed`/`partial` sem indicador visual de revisão pendente.
