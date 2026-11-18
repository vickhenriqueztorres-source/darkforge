# HQ-07: Gate visual, de desempenho e de regressão

**Objetivo:** provar que a Sede está com acabamento profissional, rápida e que nada do que existia quebrou.
**Depende de:** HQ-00 a HQ-06.
**Gate:** G-HQ7 (gate final).

## Tarefas

### HQ-07-T01: Revisão de direção de arte
Comparar a tela com `design-spec.md` item por item e com `reference/sede-conceito.png` (clima, não pixels).
Corrigir: espaçamentos irregulares entre estúdios, letreiros desalinhados, cores fora da paleta, sombras serrilhadas,
textos ilegíveis, elementos decorativos que não informam nada (remover).

### HQ-07-T02: Screenshots de referência
Salvar em `docs/studio-hq/reference/screens/` (fora do bundle do app):
- Sede com 1, 3, 12 e 24 canais a 1440 × 900.
- Sede com 12 canais a 1280, 1920 e 375 (mobile/lista).
- Foco num estúdio "trabalhando", num "aguardando você", num "em obras" e num "desconectado".
- Office3D de um canal (comparar com o antes).

### HQ-07-T03: Desempenho
Com `?perf=1`: FPS e draw calls com 12 e 24 canais; tempo até o primeiro quadro; memória após 5 min aberto
(sem crescer continuamente). Anotar em `state.md` com a máquina usada.

### HQ-07-T04: Regressão
- `pnpm typecheck:web`, `pnpm --filter @darkforge/web test:studio`, `pytest`.
- Fluxo manual do escritório atual: abrir canal, clicar sala, clicar agente, rodar agente, aprovar.
- Realtime: disparar um run num canal e ver o estúdio dele mudar na Sede em até 2 s.

### HQ-07-T05: Documentação
Atualizar `docs/studio-ui/README.md` com um parágrafo e link para `docs/studio-hq/`, marcar todos os
subplanos em `state.md` e listar desvios do plano.

## Gate G-HQ7
- [ ] Checklist do `design-spec.md` §10 ("O que evitar") sem nenhum item violado
- [ ] Números de desempenho dentro do orçamento de `plan.md` §8
- [ ] Todos os testes e checagens passando
- [ ] Screenshots salvos e `state.md` completo
- [ ] PR aberto de `feat/sede-canais` para `main` com resumo e screenshots
