# UI-07 — Qualidade e gate final

**Objetivo:** provar que o studio funciona, é seguro, acessível e rápido.  
**Depende de:** UI-00 a UI-06.  
**Gate:** G-UI7.

## Tarefas

### UI-07-T01 — E2E do fluxo completo
Com agentes fake determinísticos: novo vídeo → dados + pesquisa → estratégia → aprovar oportunidade → títulos, roteiro e thumbnail → aprovar brief → edição → publicação → aprovar plano → marcar como publicado. Verificar a cena e os painéis a cada passo.  
**Teste:** E2E verde em CI.

### UI-07-T02 — Caos e recovery
Matar o worker durante `working`, derrubar a conexão de eventos, expirar o lease e simular um provedor de modelo indisponível.  
**Teste:** nenhum estado falso de "concluído"; a UI mostra "sem sinal" ou "bloqueado" e depois se recupera.

### UI-07-T03 — Segurança
Testes de RLS em todas as tabelas novas, tentativa de escrita direta pelo navegador, prompt injection numa fonte de pesquisa e varredura de segredos nos logs.  
**Teste:** todos negados ou neutralizados.

### UI-07-T04 — Acessibilidade
Auditoria automática (axe ou equivalente) e roteiro manual: só teclado, leitor de tela, zoom de 200% e movimento reduzido.  
**Teste:** zero violações críticas.

### UI-07-T05 — Performance
Orçamento: LCP < 2,5 s com a imagem otimizada (AVIF/WebP com `sizes`), 60 fps nas transições com 8 agentes, nenhum re-render global por evento.  
**Teste:** medições registradas em `state.md`.

### UI-07-T06 — Documentação final
Atualizar `state.md`, os ADRs, o README do pacote e um guia curto "como adicionar um novo agente" (catálogo, registro, schema, layout).  
**Teste:** outra pessoa consegue adicionar um agente fake seguindo o guia.

## Gate G-UI7
- [ ] E2E e testes de caos verdes
- [ ] Segurança e RLS verdes
- [ ] A11y sem violações críticas
- [ ] Orçamento de performance atendido
- [ ] Documentação atualizada
