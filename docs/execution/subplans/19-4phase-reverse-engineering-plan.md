# Plano Geral & Subplanos — Motor de Engenharia Reversa Viral em 4 Fases (`SP-19`..`SP-23`)

**Orquestrador:** Agente Arquiteto Líder (`DarkForge Channel OS`)  
**Especialistas & Skills Ativados:**
- **`yt-outlier-title-hunter`:** Caça de Outliers, média de 20–30 vídeos, velocidade views/dia, descarte de falsos positivos, autópsia de título/capa e roteiro (`0–15s` / `15–30s` / meio / comentários).
- **`dark-channel-hacklab`:** Leis anti-cópia (Revolução Reversa), ganchos iniciais, open loops e ritmo de retenção.
- **`eugene-schwartz`:** Engenharia de Mecanismo Transferível (`Tema + Ângulo + Emoção + Estrutura + Formato`), consciência de público e promessa inédita.
- **`vibe-coding-toolkit` (Ponytail + RTK + Caveman):** Menor diff cirúrgico, zero duplicação, fronteira `core/` pura, RLS obrigatório (`FORCE ROW LEVEL SECURITY`), e bloqueio de avanço sem validação 100% do gate anterior.

---

## Plano Geral (Visão Ponta a Ponta)

Transforma os 4 passos manuais de engenharia reversa do documento em um fluxo determinístico, auditável e anti-plágio integrado ao workspace e ao canal ativo:

1. **Fase 1 (`SP-19`) — Filtro de Seleção de 5–10 Canais de Referência (6 Critérios Obrigatórios):**
   - `same_market_language` (mesmo idioma/mercado)
   - `recent_traction` (vídeos novos performando nos últimos 30–90d)
   - `repeat_hit_consistency` (mais de 1 vídeo com tração, evitando sorte isolada)
   - `feasible_format` (estilo de produção executável pelo operador)
   - `target_audience_fit` (audiência-alvo compatível com `ChannelProfileVersion`)
   - `fame_independence` (resultado vindo de tema/formato e **não** de celebridade/marca gigante onde tudo bate 500k sem pico relativo)
2. **Fase 2 (`SP-20`) — Cálculo Real de Outliers (`20–30` vídeos), Velocidade & Filtro Falso Positivo:**
   - Calcula $\text{Média do canal} = \frac{\sum \text{views últimos 20–30 vídeos}}{N}$.
   - Isola 3–5 outliers por canal com multiplicador `>= 3.0x` (ou `>= 2.0x` para `small_niche=True`).
   - Calcula $\text{Velocidade} = \frac{\text{Views atuais}}{\max(1, \text{Dias desde upload})}$, priorizando `30–90` dias e sinal de presença em Sugeridos.
   - Descarta falsos positivos (`breaking_news`, `celebrity_collab`, `channel_authority_only`) e exige **convergência multi-canal (`>= 2` canais distintos)**.
3. **Fase 3 (`SP-21`) — Laboratório de Autópsia Anti-Plágio (Package + Roteiro + Comentários):**
   - **A. Título & Capa (Package):** extrai equação sintática da promessa (tensão/risco, palavras de curiosidade, keywords no início) + mecanismo visual da capa (foco único, "pergunta visual", emoção, complementaridade sem repetir título), travando cópia literal com `ORIG-001`.
   - **B. Roteiro & Retenção:** estrutura e audita `0–15s` (Hook: 1ª frase, 1ª imagem, confirmação da promessa), `15–30s` (conflito/valor imediato antes do contexto), `Arquitetura do Meio` (blocos, ritmo, *open loops*, viradas e provas visuais) e **Mineração de Comentários** (dúvidas, reclamações *"faltou explicar..."*, pedidos de continuação).
4. **Fase 4 (`SP-22`) — Mecanismo Transferível, Banco (`0013`) & Lote de Teste (Impressões / CTR / Retenção 30s):**
   - Cruza `10–20` autópsias de canais distintos -> extrai $\text{Tema} + \text{Ângulo} + \text{Emoção} + \text{Estrutura} + \text{Formato} = \text{Mecanismo Transferível}$.
   - Troca para um tema validado do seu canal, muda o ângulo preenchendo lacuna de comentários, cria título/capa/roteiro 100% inéditos e registra **Lote de Teste** para medir `Impressões`, `CTR` e `Retenção aos 30s` (`SP-03`).
5. **Interface & Entrega (`SP-23`):** Aba interativa das 4 Fases em `Pesquisa` (`apps/web/src/app/page.tsx`) ligada direto ao `EpisodeBrief`.

---

## Subetapas & Gates Obrigatórios (Regra: só avança após 100% verde)

| Subetapa | Escopo & Entregáveis | Gate de Validação | Status |
|---|---|---|---|
| **SP-19** | `core/research/channel_selector.py` + `tests/unit/test_sp19_channel_selector.py` | **G19:** 6 critérios obrigatórios + bloqueio de canal celebridade + seleção 5–10 canais | DONE |
| **SP-20** | `core/research/viral_outlier_analyzer.py` + `OfficialYouTubeAdapter.fetch_channel_last_20_30_videos` + `tests/unit/test_sp20_viral_outliers.py` | **G20:** Média exata 20–30 vídeos, `3x`/`2x` nicho menor, `views/dia`, descarte falsos positivos e convergência `>= 2` canais | DONE |
| **SP-21** | `core/research/video_autopsy.py` + `OfficialYouTubeAdapter.fetch_public_video_comments` + `tests/unit/test_sp21_video_autopsy.py` | **G21:** Autópsia Package + `0–15s`/`15–30s`/Meio + mineração de lacunas em comentários + anti-plágio | DONE |
| **SP-22** | `core/research/transferable_mechanism.py` + `migrations/0013_sp19_reverse_engineering_engine.sql` + `reverse_engineering_repo.py` + `reverse_engineering_service.py` + `apps/api/routes/sp22.py` + `tests/integration/test_sp22_live_reverse_engineering.py` | **G22:** Persistência RLS ao vivo no Supabase + cruzamento `10–20` outliers -> Mecanismo Transferível -> Lote de Teste + contrato segurança | DONE |
| **SP-23** | `apps/web/src/lib/api.ts` + `apps/web/src/app/page.tsx` + `docs/execution/state.md` | **G23:** `pnpm typecheck:web` + `pnpm build:web` + suíte completa de testes passando 100% | DONE |
