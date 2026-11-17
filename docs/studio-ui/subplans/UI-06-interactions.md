# UI-06 — Interações e aprovação

**Objetivo:** permitir operar a equipe pela tela com segurança e histórico.  
**Depende de:** UI-02, UI-05.  
**Gate:** G-UI6.

## Tarefas

### UI-06-T01 — Criar content item
Ação "Novo vídeo" com título de trabalho; dispara `pesquisa` (e `dados`, se o insight estiver velho).  
**Teste:** gera content item e runs com idempotência; duplo clique não duplica.

### UI-06-T02 — Iniciar, cancelar e reexecutar agente
No card ou na gaveta: "Executar agora", "Cancelar" (se o job aceitar) e "Tentar de novo" (falha recuperável).  
**Teste:** cancelar respeita o estado do job; reexecutar cria um novo `attempt` ligado ao anterior.

### UI-06-T03 — Aprovar ou rejeitar
Para `opportunity`, brief e `publication_plan`: aprovar, rejeitar ou pedir mudanças, com motivo. Registra `approvals` com versão e libera ou cancela os handoffs.  
**Teste:** aprovar a versão 2 não aprova a 3; rejeitar cancela os handoffs pendentes; não dá para aprovar output `needs_review` sem confirmar o aviso.

### UI-06-T04 — Revisão humana
Outputs `needs_review` mostram o motivo (similaridade, fonte inválida, tema proibido). O usuário pode editar e salvar como nova versão (autor humano) ou descartar.  
**Teste:** a edição cria uma nova versão e não sobrescreve.

### UI-06-T05 — Configurar a equipe do canal
Ativar ou desativar agentes, nome de exibição, avatar, política de modelo (local ou externo com consentimento) e orçamento.  
**Teste:** agente desativado não recebe handoff; política externa sem consentimento é bloqueada.

### UI-06-T06 — Publicação manual
No plano aprovado: "Marcar como publicado" com a URL do vídeo, que move o content item para `publicado_manual`. Não existe botão de publicar no YouTube.  
**Teste:** a URL é validada; o evento é registrado.

## Gate G-UI6
- [ ] Toda ação gera registro auditável
- [ ] Aprovação versionada controla os handoffs
- [ ] Nenhuma ação publica automaticamente
