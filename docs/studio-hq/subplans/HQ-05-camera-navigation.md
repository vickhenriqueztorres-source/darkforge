# HQ-05: Câmera, navegação e URL

**Objetivo:** ir da Sede ao estúdio e ao escritório do canal, e voltar, de forma fluida e com link compartilhável.
**Depende de:** HQ-03 e HQ-04.
**Referência:** `plan.md` §6 e D9, `design-spec.md` §7.
**Gate:** G-HQ5.

## Tarefas

### HQ-05-T01: `HQScene.tsx`
`Canvas` carregado com `dynamic(..., { ssr: false })`, mesmas opções do `OfficeScene` (sombras, `dpr [1,2]`,
fallback sem WebGL), `frameloop` conforme `plan.md` §8, pausa por `IntersectionObserver` (copiar o padrão do `Office3D`).

### HQ-05-T02: `CameraRig.tsx`
- Câmera ortográfica isométrica (`ISO_AZIMUTH`), `OrbitControls` com giro limitado igual ao Office3D,
  **pan habilitado** na Sede (limitado a `bounds`), zoom 0,6× a 2,5× do enquadramento.
- `fitBuilding(bounds, size)`: zoom com 6% de margem; recalcular no resize.
- `flyTo(slot)`: anima `target` e `zoom` em 600 ms (`easeInOutCubic`), desligando os controles durante a animação;
  com movimento reduzido, corte instantâneo.
- `flyBack()`: volta ao enquadramento da Sede preservando o pan anterior.

### HQ-05-T03: Estados de navegação
Máquina simples em `useHQNavigation.ts`: `overview` → `focus(channelId)` → `enter(channelId)`.
- Clique ou Enter num estúdio → `focus`.
- "Entrar no estúdio", duplo clique ou Enter no estúdio já focado → `enter`: troca para o `Office3D` do canal.
- `Esc`, botão "Voltar" ou Voltar do navegador → passo anterior.

### HQ-05-T04: URL
- `?view=sede` → Sede; `?view=sede&focus=<id>` → foco; `?channel=<id>` (sem `view`) → escritório do canal (comportamento atual).
- Usar `router.push` em `enter` e `router.replace` em `focus` (o foco não deve encher o histórico).
- Abrir a URL direto deve restaurar o estado (inclusive o foco com a câmera já posicionada, sem animação).
- Id de canal inexistente → Sede com aviso "Canal não encontrado neste workspace".

### HQ-05-T05: Integração no `StudioWorkspace` e no menu
- Seletor segmentado **Sede | Estúdio do canal** na barra superior do studio (ao lado do seletor de canal).
- Item do menu lateral "Estudio 2.5D" renomeado para **"Sede & Estúdios"**; ao clicar, abre `?view=sede`.
- No escritório do canal, botão "← Sede" no header do `Office3D`.

## Testes
- Unitário: `useHQNavigation` (transições e URL resultante) e `fitBuilding` (zoom para 1, 12 e 24 canais em 3 tamanhos de tela).

## Gate G-HQ5
- [ ] Sede → foco → escritório → voltar → voltar funciona com mouse, teclado e botão Voltar do navegador
- [ ] Recarregar a página em cada estado restaura o mesmo estado
- [ ] Animação de câmera sem tranco; instantânea com `prefers-reduced-motion`
- [ ] Nenhuma regressão no fluxo atual de `?channel=<id>`
