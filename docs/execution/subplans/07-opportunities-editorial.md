# SP-07 — Opportunity Engine e Editorial Studio

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-03, SP-04, SP-05 e SP-06  
**Desbloqueia:** SP-08  
**Objetivo:** fechar o ciclo de decisão editorial: evidências → oportunidade → feedback → brief aprovado → calendário/exportação.

## 1. Escopo

Analistas, score versionado, geração de oportunidades, explicação, feedback, copies, briefs, versões, aprovação, calendário e exportação.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-07-T01 | Implementar contratos de analistas | Canal, vídeo, audiência, concorrência, título, capa e copy | Cada analista declara entradas, saídas, limitações e versão |
| SP-07-T02 | Implementar score e confiança | Componentes, pesos, versão e explicação | Score não é apresentado como previsão de views/viralização |
| SP-07-T03 | Implementar geração de oportunidades | Tema, episódio, ângulo, diferenciação e evidências | Usa perfil, pesquisa e RAG permitidos; pode declarar dados insuficientes |
| SP-07-T04 | Implementar painel “Por quê?” | Fontes, contexto, score, limitações e modelo | Usuário consegue auditar a recomendação antes de decidir |
| SP-07-T05 | Implementar decisões e feedback | Aprovar, rejeitar, editar, arquivar e motivos | Histórico registra autor, data e versão; feedback não é chamado de fine-tuning |
| SP-07-T06 | Implementar modelo de brief | Objetivo, público, ângulo, estrutura, títulos, CTA e fontes | Brief referencia oportunidade, canal, perfil e versões de contexto |
| SP-07-T07 | Implementar geração de copy assistida | Hooks, outlines, descrições, roteiros e CTAs com proveniência | Geração registra modelo/prompt/fontes e não aprova automaticamente |
| SP-07-T08 | Implementar versões e aprovação | Rascunho, revisão, aprovação e congelamento | Aprovar congela a versão; editar depois cria nova versão |
| SP-07-T09 | Implementar calendário editorial | Agendar, mover, filtrar e status | Não publica automaticamente; preserva canal e brief relacionado |
| SP-07-T10 | Implementar exportação | Brief e dados em formato portátil | Exportação contém versão, data e fontes permitidas |
| SP-07-T11 | Construir Editorial Studio UI | Lista, detalhe, edição, decisões, calendário e histórico | Fluxo é utilizável por teclado e estados de erro são claros |
| SP-07-T12 | Criar testes editoriais e de IA | T-ED-001, T-AI-001 e casos de poucos dados | Recomendação sem evidência, cópia e prompt injection são bloqueados/sinalizados |

## 3. Regras de negócio

- Toda oportunidade pertence a um canal e a uma versão de perfil.
- Tema proibido e restrição de direitos têm precedência sobre a geração.
- Score é uma ferramenta de triagem, não garantia de desempenho.
- Rejeição não apaga a sugestão nem seu histórico.
- Brief aprovado é imutável; nova edição é nova versão.
- Nenhuma geração de IA inicia produção por conta própria.

## 4. Testes mínimos

- Canal com perfil completo versus perfil incompleto.
- Poucos dados, fontes contraditórias e contexto insuficiente.
- Oportunidade com fonte fora do workspace ou sem direitos.
- Edição de oportunidade e de brief após aprovação.
- Rejeição com motivo e histórico de decisões.
- Calendário com vários canais e mudança de data.
- Exportação sem vazamento de fonte privada não autorizada.
- Prompt injection e promessa sem evidência.

## 5. Gate G7

Só avançar quando:

- oportunidade gerada tem evidências, score, confiança e limitações;
- usuário consegue rejeitar, editar e aprovar;
- brief aprovado congela versão e preserva histórico;
- calendário e exportação funcionam sem publicação automática;
- OPP-001–006 e EDIT-001–006 têm evidência;
- ADR-007/008/009 estão satisfeitos.
