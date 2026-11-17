# ADR-017 — Automação Assistida de Navegador no YouTube Studio Trends (Emenda ao ADR-005)

- **Status:** ACCEPTED (Escopo estrito, conta própria, Human-in-the-Loop)
- **Subplanos:** SP-10..SP-14
- **Altera parcialmente:** [ADR-005](ADR-005.md)

## Contexto
A aba **Analytics > Trends / Research** do YouTube Studio (`Top searches`, `Audience interest`, `Content gaps` e `Watched by my viewers`) não possui endpoints públicos na YouTube Data API v3 nem na YouTube Analytics API v2.

## Decisão
Permitir uso de **Playwright** em worker local dedicado (`workers/studio_scraper` / `adapters/studio_browser`) operando exclusivamente sobre a sessão autenticada manualmente pelo operador do canal (`launch_persistent_context`), sob as seguintes invariantes obrigatórias:

1. **Zero armazenamento de senha Google:** credenciais Google/Cookies não são salvos em `.env` nem em Postgres.
2. **Human-in-the-Loop obrigatório:** o usuário efetua login e 2FA manualmente na janela do navegador. Se houver expiração de sessão, redirecionamento para `accounts.google.com`, pedido de 2FA ou desafio anti-bot/CAPTCHA, o job é marcado como **`BLOCKED`** (`STUDIO_AUTH_REQUIRED`) sem tentativa de contorno automático.
3. **Rate-limiting conservador:** limite configurável por hora (`max_runs_per_hour`, padrão `6`) e atrasos entre ações para proteção da conta.
4. **Cálculo de Outlier Score transparente:** o baseline (`3x`, `5x+`) é calculado preferencialmente sobre vídeos públicos via YouTube Data API v3 (`QuotaPool.PUBLIC_RESEARCH`) ou amostra pública explícita registrada em `channel_baseline_views`, e `Content gaps` são marcados como **hipótese a validar** (`is_hypothesis = true`).
5. **Isolamento de camadas:** Playwright não pode ser importado em `core/` nem em `apps/web/`.
