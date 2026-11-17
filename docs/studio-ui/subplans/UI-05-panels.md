# UI-05 — Painéis

**Objetivo:** construir os painéis da referência com dados reais e estados honestos.  
**Depende de:** UI-03, UI-04.  
**Gate:** G-UI5.

## Tarefas

### UI-05-T01 — Painel do Canal
Nome do canal, visualizações, CTR e tempo médio de visualização, com delta e mini gráfico do período. Etiqueta "atualizado há X" com botão de sync (enfileira job do SP-03).  
**Teste:** `unknown` mostra "indisponível" e não 0; `stale` mostra aviso; CTR ausente não quebra o layout.

### UI-05-T02 — Painel de Oportunidade
Anel de score (valor/máx), potencial, concorrência e confiança, e o link "Por quê?" que abre as evidências e limitações do output `opportunity`. Status da aprovação visível.  
**Teste:** sem oportunidade, mostra estado vazio com a ação "Gerar oportunidade"; o score vem do output, nunca calculado na UI.

### UI-05-T03 — Painel Atividade dos Agentes
Uma linha por agente do content item ativo: indicador de status (verde = done, amarelo = working/needs_review, cinza = idle/queued, vermelho = failed/blocked) e o `summary` do último evento. Clique abre o card do agente.  
**Teste:** a ordem segue o pipeline; o status também aparece em texto, não só em cor.

### UI-05-T04 — Gaveta da sala
Agentes da sala, runs recentes (status, duração, custo estimado), últimos outputs com versão e fontes, e ações permitidas.  
**Teste:** abre e fecha por teclado; o foco volta para a sala ao fechar.

### UI-05-T05 — Card do agente
Avatar, responsabilidade, política de modelo, run atual (etapa, progresso ou "indeterminado", heartbeat), último output e histórico.  
**Teste:** heartbeat antigo mostra "sem sinal".

### UI-05-T06 — Seletor de canal e de content item
Troca o canal (a equipe toda) e o content item ativo do painel de atividade, refletindo na URL.  
**Teste:** trocar de canal não mostra dados do anterior nem por um frame.

### UI-05-T07 — Tokens visuais
Painéis em vidro fosco sobre a cena, no máximo 5 cores via tokens, tipografia nítida e contraste AA sobre a imagem (fundo do painel suficientemente opaco).  
**Teste:** a auditoria de contraste passa.

## Gate G-UI5
- [ ] Nenhum número fixo no código
- [ ] Estados unknown, stale, vazio e erro cobertos
- [ ] Contraste AA e foco visível
