# Plano de Implementação & Subetapas — Interface Web Navegável & Central de Relatórios (`SP-24`..`SP-27`)

## Arquitetura de Orquestração & Especialistas Ativados
- **Orquestrador:** Controla execução sequencial com validação obrigatória por Gate (`G24` → `G25` → `G26` → `G27`). Nenhuma subetapa inicia antes da anterior estar 100% validada e segura.
- **Especialistas & Skills aplicadas:**
  - `vibe-coding-toolkit` + `Ponytail`: menor diff suficiente, reuso de repositórios e `export_safe_diagnostics`, zero abstração especulativa, zero segredo no cliente.
  - `yt-outlier-title-hunter` + `eugene-schwartz`: exibição clara das 4 Fases (Filtro 6 critérios, Média 20–30 + Outlier Score + Views/Dia, Autópsia Package/Retenção/Comentários, Mecanismo Transferível + Lote de Teste).
  - `a11y-debugging`: semântica HTML (`<label htmlFor>`, `<main>`, `<nav aria-label>`, `<section>`, contraste, foco visível, tap-targets ≥ 40px).
  - `browser` (subagent): verificação ponta-a-ponta em navegador real (`http://127.0.0.1:3000`) sem erros de console, CORS ou 500, com conferência via `BROWSER_HOST_FACTS`.

---

## Subetapa SP-24 (`Gate G24`) — API de Relatórios Consolidados & Exportação Executiva
**Objetivo:** Expor visão unificada multi-tenant do workspace (Canais, 4 Fases Reverse Engineering, Studio Trends, Google Trends, Oportunidades + 4 Analistas, Briefs, Calendário e Diagnóstico Sanitizado) + exportação `.md`.
- **Arquivos:**
  - `adapters/supabase_db/reverse_engineering_repo.py` (`list_viral_outliers`)
  - `core/research/reverse_engineering_service.py` (`viral_outliers` em `list_state`)
  - `adapters/supabase_db/studio_trends_repo.py` (`list_latest_items` ou leitura de termos/outliers do último run)
  - `apps/api/routes/sp24.py` (`GET /api/v1/reports/overview`, `GET /api/v1/reports/executive.md`)
  - `apps/api/main.py` (registrar `sp24_router`)
  - `tests/integration/test_sp24_live_reports_api.py`
- **Validação Gate G24:** `pytest tests/integration/test_sp24_live_reports_api.py tests/contracts/test_sp01_migrations_and_security.py -v` **13/13 PASSED** (live Supabase + isolamento multi-tenant `403` + zero segredos vazados).
- **Status:** `DONE`

---

## Subetapa SP-25 (`Gate G25`) — Navegação Completa no Navegador, Fases 1–4 Interativas, Aba Relatórios & A11y
**Objetivo:** Tornar o painel web totalmente navegável com auto-carregamento por aba, formulários completos das Fases 1–4 em `Pesquisa`, aba `Relatórios & Central` com 5 sub-visões, inspeção dos 4 Analistas + `score_breakdown`, exportação `.md` e impressão (`PDF`).
- **Arquivos:**
  - `apps/web/src/app/globals.css`
  - `apps/web/src/lib/api.ts`
  - `apps/web/src/app/page.tsx`
- **Validação Gate G25:** `pnpm typecheck:web` + `pnpm build:web` + `pytest tests/contracts/test_sp01_migrations_and_security.py -v` **100% verdes** (`Route / 84.2 kB`, `12/12` contratos OK).
- **Status:** `DONE`

---

## Subetapa SP-26 (`Gate G26`) — Subida de Serviços Locais & Validação ao Vivo no Navegador
**Objetivo:** Iniciar API FastAPI (`127.0.0.1:8000`) e Web Next.js (`127.0.0.1:3000`) e validar com o subagente `browser` o fluxo completo de login, navegação entre abas, renderização dos relatórios e ausência de erros de console/rede/a11y.
- **Validação Gate G26:** Verificado ao vivo em `http://127.0.0.1:3000` (via subagente `browser` e `BROWSER_HOST_FACTS`) com login Supabase Auth, criação de workspace/canal, execução das Fases 1–4 (`APROVADO` e `OUTLIER`), geração de Oportunidade, navegação por todas as abas (`Relatorios & Central` + 5 sub-abas + preview Markdown + 4 Analistas), correção de overflow/contraste e limpeza dos dados temporários de QA (`deleted_ws: 1`, `user_delete_status: 200`).
- **Status:** `DONE`

---

## Subetapa SP-27 (`Gate G27`) — Sincronização Final, Auditoria de Segurança & Entrega
**Objetivo:** Revalidar contratos e integração, atualizar `docs/execution/subplans/24-web-reports-navigation-plan.md` e `docs/execution/state.md`, confirmar URLs ativas para uso imediato pelo usuário.
- **Validação Gate G27:** `pytest tests/integration/test_sp24_live_reports_api.py tests/contracts/test_sp01_migrations_and_security.py -v` **13/13 PASSED** em `61.69s` após última edição; `pnpm typecheck:web` & `pnpm build:web` OK (`Route / 84.2 kB`); servidores locais ativos (`http://127.0.0.1:3000` e `http://127.0.0.1:8000`).
- **Status:** `DONE`
