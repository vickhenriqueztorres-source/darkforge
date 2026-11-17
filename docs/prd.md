# DarkForge Channel OS
## Product Requirements Document — PRD

**Status:** proposta para validação de produto  
**Versão:** 0.1  
**Data:** 16 de novembro de 2026  
**Documento relacionado:** [Arquitetura completa v0.2](architecture.md)  
**Tipo de entrega:** documentação; não inclui implementação da ferramenta  
**Plataforma inicial:** YouTube  
**Modelo de uso inicial:** um usuário, um PC, vários canais em um workspace

---

## 1. Resumo do produto

O **DarkForge Channel OS** é uma estação de inteligência editorial para quem administra um ou vários canais do YouTube. O produto reúne dados autorizados dos próprios canais, referências públicas, conhecimento curado e decisões editoriais em um único fluxo de trabalho.

A proposta não é apenas mostrar dashboards ou gerar textos com IA. O produto deve ajudar o usuário a responder, com evidências:

1. Como cada canal e vídeo está performando?
2. O que canais semelhantes estão publicando e quais padrões aparecem?
3. Quais temas e episódios fazem sentido para um canal específico agora?
4. Como transformar uma oportunidade aprovada em brief, copy e produção sem perder a identidade do canal?

O resultado central é um **brief editorial aprovado, rastreável e pronto para produção**, acompanhado das fontes, limitações, versões e decisões que o originaram.

### 1.1 Declaração de visão

> Dar ao operador de canais um sistema de decisão editorial que combina dados confiáveis, pesquisa de mercado e conhecimento próprio para produzir conteúdo original com mais consistência, sem esconder incertezas nem retirar o controle humano.

### 1.2 Proposta de valor

- **Uma visão única:** canais, vídeos, métricas, referências, copies e calendário deixam de ficar espalhados em planilhas, abas e anotações.
- **Decisões explicáveis:** toda recomendação mostra evidências, origem, data, filtros e limitações.
- **Identidade por canal:** cada canal tem posicionamento, voz, público, pilares e restrições próprios.
- **Pesquisa que vira ação:** referências públicas podem ser curadas e transformadas em oportunidades e briefs.
- **Conhecimento reutilizável:** copies aprovadas alimentam um RAG citável, sem treinar pesos de modelo.
- **Execução confiável:** trabalhos longos têm progresso real, pausa, retomada, cancelamento e recuperação.
- **Controle editorial:** nenhuma publicação ou produção relevante acontece sem aprovação explícita.

---

## 2. Contexto e problema

### 2.1 Situação atual

O fluxo de gestão editorial costuma exigir que o usuário alterne entre YouTube Studio, pesquisas manuais, planilhas, documentos de referência, ferramentas de IA e o pipeline de produção. Essa fragmentação causa:

- dificuldade para comparar canais e vídeos com o mesmo critério;
- perda de contexto entre uma pesquisa e a decisão de pauta;
- recomendações genéricas que ignoram a identidade do canal;
- cópias e referências sem curadoria, origem ou controle de uso;
- métricas ausentes interpretadas como zero ou como mau desempenho;
- retrabalho para transformar uma ideia em brief e produção;
- jobs longos sem visibilidade, recuperação ou confirmação confiável;
- risco de copiar referências em vez de aprender com seus padrões.

### 2.2 Problema a resolver

O usuário precisa decidir **o que produzir, para qual canal, com qual abordagem e com base em quais evidências**, sem precisar reconstruir esse raciocínio a cada novo vídeo.

O problema não é falta de dados ou de modelos de IA isoladamente. É a ausência de um sistema que conecte dados, pesquisa, conhecimento, decisão e execução com proveniência e controle.

### 2.3 Hipóteses de produto

| Hipótese | Como será validada |
|---|---|
| Um Channel Profile por canal aumenta a qualidade das recomendações | Comparar sugestões com e sem Channel Profile em testes de usuário |
| Evidências e limitações aumentam a confiança | Medir inspeção de fontes, compreensão e taxa de aprovação/rejeição informada |
| Curadoria de copies melhora a utilidade do RAG | Avaliar recall, citações e rejeição em um conjunto de testes versionado |
| Um brief estruturado reduz retrabalho de produção | Medir tempo até brief aprovado e número de correções posteriores |
| Progresso e recovery reais reduzem abandono de jobs | Medir conclusão após reinício, retries e falsos sucessos |

---

## 3. Princípios de produto

1. **Evidência antes de recomendação.** Nenhuma sugestão deve parecer mais certa do que os dados permitem.
2. **Ausência não é zero.** Métrica indisponível, atrasada ou não aplicável deve ser identificada como tal.
3. **Identidade antes de volume.** Uma ideia só é válida quando faz sentido para o canal selecionado.
4. **Curadoria antes de indexação.** Conteúdo importado não entra automaticamente no contexto confiável.
5. **Originalidade obrigatória.** Referências servem para análise e aprendizado, não para reprodução literal.
6. **Aprovação humana nos pontos de compromisso.** Briefs e produções exigem decisão explícita.
7. **Progresso real, não teatro de interface.** Um job só termina quando seu resultado foi persistido e validado.
8. **Falha visível e recuperável.** Erros parciais, quota, rede e indisponibilidade devem ser compreensíveis e acionáveis.
9. **Privacidade por desenho.** O usuário sabe quais dados saem do PC e para qual provedor.
10. **Menos automação com mais controle.** O produto prioriza um fluxo editorial confiável a uma coleção de agentes autônomos.

---

## 4. Público e usuários

### 4.1 Usuário primário

**Criador/operador editorial independente** que administra um ou vários canais, participa da escolha de pautas e precisa transformar análise em produção.

Características:

- tem conhecimento do próprio nicho, mas não necessariamente de análise de dados;
- trabalha com volume suficiente de vídeos para sentir perda de contexto;
- usa referências de outros canais, mas quer preservar originalidade;
- pode ter copies, roteiros e aprendizados espalhados em arquivos;
- precisa de uma aplicação local no PC, com interface no navegador;
- aceita IA como apoio, mas quer revisar decisões importantes.

### 4.2 Usuários secundários futuros

- editor ou estrategista responsável por revisar briefs;
- gestor de portfólio de canais;
- roteirista que consome copies e referências aprovadas;
- operador de produção que acompanha artifacts e jobs.

Esses perfis não implicam colaboração multiusuário no MVP. O modelo de workspaces e permissões deve existir desde o início para não criar uma migração insegura depois.

### 4.3 Não é o foco inicial

- agências com dezenas de usuários e permissões complexas;
- usuários que procuram publicação totalmente automática;
- quem deseja obter analytics privados de concorrentes;
- quem espera previsão garantida de viralização;
- equipes que precisam de dezenas de plataformas no primeiro ciclo.

### 4.4 Jobs to be done

| Quando... | Quero... | Para... |
|---|---|---|
| começo a trabalhar em um canal | ver seu desempenho, frescor e pendências | saber onde investigar primeiro |
| preciso escolher uma pauta | pesquisar referências e comparar padrões | encontrar uma oportunidade relevante |
| encontro um tema promissor | entender as evidências e os riscos | decidir se vale produzir |
| tenho copies e aprendizados | organizar, aprovar e recuperar esse conhecimento | não recomeçar do zero |
| aprovo uma ideia | gerar um brief versionado | alinhar produção e preservar a decisão |
| um processo demora ou falha | acompanhar, pausar, retomar ou corrigir | não perder trabalho nem duplicar resultados |

---

## 5. Objetivos e não objetivos

### 5.1 Objetivos do MVP

- Centralizar vários canais e seus perfis editoriais.
- Conectar canais próprios por OAuth e sincronizar dados disponíveis.
- Exibir analytics de portfólio, canal e vídeo com origem e frescor.
- Pesquisar canais e vídeos públicos semelhantes com evidências rastreáveis.
- Analisar estruturalmente títulos e fazer análise básica de capas.
- Importar, revisar, aprovar e recuperar copies em uma base RAG citável.
- Gerar oportunidades com score, justificativa, limitações e contexto.
- Criar, editar, aprovar, versionar e exportar briefs.
- Manter calendário editorial e histórico de decisões.
- Executar jobs persistentes com logs, pausa, retomada, cancelamento e recovery.
- Integrar um brief aprovado ao pipeline DarkForge sem criar uma segunda fonte de verdade.

### 5.2 Não objetivos do MVP

- Publicação automática ou alteração de vídeos sem autorização.
- Previsão de views, receita ou viralização.
- Fine-tuning de modelos.
- Colaboração multiusuário completa.
- Obtenção de métricas privadas de concorrentes.
- Scraping indiscriminatório ou contorno de restrições de plataformas.
- Geração final de capas prontas para publicação.
- Dezenas de plataformas e integrações simultâneas.
- Automação autônoma sem supervisão.
- Operação totalmente offline com escrita e conclusão de jobs.

---

## 6. Métricas de sucesso

As metas abaixo são **propostas iniciais para validação**, não resultados observados. O baseline deve ser medido durante o piloto.

### 6.1 Métrica norte

**Briefs aprovados por semana com evidências completas e sem retrabalho causado por dados incorretos.**

Essa métrica combina valor editorial, qualidade de decisão e confiabilidade, em vez de contar apenas gerações de IA.

### 6.2 Indicadores

| Indicador | Definição | Meta inicial proposta |
|---|---|---|
| Ativação | Usuário conecta um canal, conclui um sync e visualiza dados com origem | Medir no piloto; meta de fluxo sem assistência |
| Tempo até o primeiro valor | OAuth início → primeiro dashboard utilizável | Até 15 minutos em condições normais, a validar |
| Cobertura de proveniência | Recomendações com fontes, data, filtros e limitações | 100% |
| Honestidade de métricas | Métricas indisponíveis exibidas como desconhecidas | 100%; nunca convertidas em zero |
| Sucesso de sync | Jobs de sync concluídos sem erro não tratado | Baseline e meta por tipo de sync |
| Frescor | Canais com sincronização dentro da política configurada | Medir por canal e fonte |
| Qualidade de RAG | Recall e precisão de citações no conjunto de avaliação | Threshold aprovado antes do piloto |
| Utilidade editorial | Oportunidades aprovadas, editadas ou rejeitadas com motivo | Medir distribuição e motivos |
| Eficiência | Tempo da pesquisa ao brief aprovado | Reduzir contra o fluxo manual baseline |
| Confiabilidade de jobs | Jobs recuperados sem duplicar efeitos | 100% nos cenários de teste obrigatórios |
| Falso sucesso | Job marcado como concluído sem resultado persistido | Zero |
| Isolamento | Acessos indevidos entre workspaces | Zero |
| Custo | Custo de IA, embeddings, Storage e egress por brief aprovado | Teto configurável e medido |

### 6.3 Guardrails

O produto não deve otimizar aprovação a qualquer custo. Também devem ser monitorados:

- taxa de rejeição por baixa qualidade;
- reclamações de recomendações genéricas;
- similaridade indevida com referências;
- falhas de quota e latência;
- custo por pesquisa e por geração;
- frequência de dados desatualizados;
- abandono após erro ou indisponibilidade.

---

## 7. Escopo e priorização

### 7.1 Legenda

- **MVP:** necessário para o primeiro fluxo completo de valor.
- **P1:** próxima evolução depois do MVP validado.
- **P2:** exploração futura, sem compromisso de entrega.
- **Fora:** não planejado para o ciclo atual.

### 7.2 Mapa de escopo

| Capacidade | Prioridade | Observação |
|---|---|---|
| Workspace, autenticação e isolamento | MVP | Pré-requisito de segurança |
| Vários canais e perfis editoriais | MVP | Um usuário no primeiro ciclo |
| OAuth e sync YouTube | MVP | APIs oficiais e dados autorizados |
| Dashboard de portfólio/canal/vídeo | MVP | Sem inventar métricas |
| Pesquisa pública e referências curadas | MVP | Com quota e evidências |
| Análise de títulos | MVP | Estrutural e explicável |
| Análise básica de capas | MVP | OCR/visão quando disponível |
| Biblioteca de copies e curadoria | MVP | L0–L3 |
| RAG com citações | MVP | Fontes aprovadas e filtros |
| Oportunidades e score | MVP | Explicável, sem promessa de desempenho |
| Briefs, versões e aprovação | MVP | Aprovação congela a versão |
| Calendário editorial | MVP | Planejamento, não publicação automática |
| Exportação de brief/dados | MVP | Formato portátil |
| Fila, logs e recovery | MVP | Sem falso sucesso |
| Integração DarkForge | MVP condicionado | Depende dos contratos reais do núcleo |
| Backup e restore | MVP operacional | Postgres e Storage |
| Colaboração e comentários | P1 | Após validar o fluxo individual |
| Publicação assistida | P1/P2 | Sempre com autorização |
| Novas plataformas | P2 | Via adapters |
| Previsão de desempenho | Fora do MVP | Exigiria evidência e escopo próprios |
| Fine-tuning | Fora do MVP | RAG atende ao objetivo inicial |
| Automação autônoma | Fora | Não é o valor central |

---

## 8. Requisitos funcionais

### 8.1 Autenticação, workspace e permissões

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| AUTH-001 | O usuário deve autenticar-se antes de acessar dados do workspace | MVP | Sessão válida é exigida; rotas e dados não ficam públicos |
| AUTH-002 | O sistema deve selecionar um workspace e vários canais dentro dele | MVP | O workspace ativo fica visível e todas as consultas respeitam esse contexto |
| AUTH-003 | O sistema deve isolar dados entre workspaces | MVP | Testes com dois usuários/workspaces não retornam dados cruzados em telas, APIs, buscas ou arquivos |
| AUTH-004 | O sistema deve distinguir autenticação do produto e conexão OAuth do YouTube | MVP | Revogar o YouTube não encerra a sessão; trocar de conta não mistura conexões |
| AUTH-005 | O usuário deve conseguir encerrar a sessão e revisar conexões ativas | MVP | Logout invalida a sessão local; conexões exibem estado e última validação |
| AUTH-006 | O sistema deve distinguir “sem dados” de “sem permissão” e “falha de consulta” | MVP | Mensagens e estados não apresentam vazio genérico para erro ou bloqueio |

### 8.2 Canais e identidade editorial

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| CH-001 | Criar e editar um Channel Profile | MVP | Nome, plataforma, idioma, país, fuso, nicho, posicionamento e objetivos podem ser salvos |
| CH-002 | Configurar público, pilares, voz, formatos e restrições | MVP | O perfil aceita público, dores, desejos, tom, temas proibidos e referências permitidas |
| CH-003 | Versionar mudanças do perfil | MVP | Editar cria uma nova versão; recomendações antigas continuam associadas à versão usada |
| CH-004 | Registrar mudança de tema ou posicionamento | MVP | A mudança tem data e não reescreve o histórico editorial |
| CH-005 | Conectar um canal próprio por OAuth | MVP | O usuário autoriza escopos mínimos e vê sucesso, pendência ou revogação |
| CH-006 | Sincronizar catálogo e métricas disponíveis | MVP | Sync incremental e backfill têm estado, cursor, progresso e última atualização |
| CH-007 | Exibir frescor e erros parciais | MVP | Cada visão mostra origem, período, última sincronização e dados que falharam |
| CH-008 | Desconectar ou revogar um canal | MVP | A ação explica retenção, exclusão e impacto em dados e jobs relacionados |

### 8.3 Analytics Center

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| AN-001 | Exibir dashboard do portfólio | MVP | O usuário compara canais por período e identifica mudanças relevantes |
| AN-002 | Exibir dashboard de um canal | MVP | O usuário filtra período, formato e pilares disponíveis sem perder o contexto do canal |
| AN-003 | Exibir ficha detalhada de vídeo | MVP | A ficha reúne métricas, metadados, análises, referências e histórico disponível |
| AN-004 | Representar métricas ausentes corretamente | MVP | `unknown`, atrasado, parcial e não aplicável têm apresentação distinta de zero |
| AN-005 | Mostrar origem e semântica da métrica | MVP | O usuário consegue entender fonte, data de atualização, dimensões e limitações |
| AN-006 | Comparar períodos e vídeos compatíveis | MVP | O sistema impede ou sinaliza comparações com dimensões/granularidades incompatíveis |
| AN-007 | Preservar histórico e revisões | MVP | Dados tardios ou revisados não apagam silenciosamente a versão anterior |

### 8.4 Research Explorer

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| RES-001 | Iniciar uma pesquisa com objetivo e filtros | MVP | Canal, idioma, período, formato e objetivo ficam registrados no research run |
| RES-002 | Encontrar canais e vídeos públicos semelhantes | MVP | Cada candidato mostra por que foi considerado semelhante |
| RES-003 | Exibir evidências de títulos, capas e publicações | MVP | O usuário abre a referência original e vê data e origem do snapshot |
| RES-004 | Curar referências | MVP | O usuário aprova, rejeita, arquiva e adiciona notas sem perder a trilha |
| RES-005 | Controlar quota e custo da pesquisa | MVP | O usuário vê orçamento/estado; pesquisa não bloqueia indefinidamente o sync próprio |
| RES-006 | Distinguir dados públicos de analytics privados | MVP | Nenhuma métrica privada de concorrente é apresentada como fato |
| RES-007 | Repetir pesquisa sem duplicar resultados | MVP | Retry e mesma intenção respeitam idempotência e deduplicação |

### 8.5 Title e Thumbnail Intelligence

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| TITLE-001 | Analisar estrutura de títulos | MVP | O sistema identifica padrões como promessa, especificidade, formato e gancho, com exemplos |
| TITLE-002 | Gerar alternativas originais de título | MVP | Cada alternativa indica canal, objetivo, referências usadas e diferenciação |
| THUMB-001 | Analisar capas com OCR/visão quando disponível | MVP | Texto, composição e elementos detectados são apresentados como análise, não verdade absoluta |
| THUMB-002 | Comparar padrões visuais sem copiar | MVP | O sistema aponta semelhanças e propõe direção diferenciada |
| THUMB-003 | Sinalizar indisponibilidade de visão/OCR | MVP | Falta de modelo ou imagem não gera análise inventada nem bloqueia todo o fluxo |
| ORIG-001 | Checar similaridade indevida | MVP | Resultados muito próximos são sinalizados para revisão antes da aprovação |

### 8.6 Knowledge/RAG Studio

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| KNOW-001 | Importar copies e fontes com metadados | MVP | Tipo, canal, idioma, origem, direitos e contexto podem ser registrados |
| KNOW-002 | Revisar e classificar fontes em L0–L3 | MVP | O usuário entende o significado de cada nível e o uso permitido no RAG |
| KNOW-003 | Deduplicar e versionar fontes | MVP | Reimportação não cria duplicatas silenciosas nem apaga histórico |
| KNOW-004 | Indexar somente conteúdo permitido | MVP | L0 não entra por padrão; fonte arquivada deixa de aparecer em novas buscas |
| KNOW-005 | Recuperar conhecimento com filtros | MVP | Canal, idioma, status, direitos e coleção são respeitados na busca |
| KNOW-006 | Exibir citações e contexto utilizado | MVP | O usuário abre os chunks/fontes usados em uma geração |
| KNOW-007 | Excluir fonte e derivados | MVP | Chunks, embeddings, caches e objetos associados entram no fluxo de exclusão |
| KNOW-008 | Avaliar qualidade do retrieval | MVP operacional | Conjunto de testes mede recall, citações e comportamento após arquivamento |

### 8.7 Opportunity Engine

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| OPP-001 | Gerar oportunidades para um canal | MVP | A geração usa perfil, pesquisa e conhecimento permitido do canal selecionado |
| OPP-002 | Explicar score e confiança | MVP | O usuário vê componentes, pesos/versão, evidências e limitações |
| OPP-003 | Apresentar episódio/tema e diferenciação | MVP | A sugestão não é apenas um título genérico; inclui ângulo e razão editorial |
| OPP-004 | Aprovar, rejeitar, editar ou arquivar | MVP | A decisão registra autor, data, motivo opcional e versão |
| OPP-005 | Aprender com feedback sem treinar pesos | MVP | Feedback fica disponível para análise e futuras regras/curadoria, sem alegar fine-tuning |
| OPP-006 | Declarar incerteza e dados insuficientes | MVP | O sistema pode recomendar não agir ou pedir mais contexto |

### 8.8 Editorial Studio e calendário

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| EDIT-001 | Criar brief a partir de oportunidade | MVP | O brief referencia oportunidade, canal, perfil e fontes utilizadas |
| EDIT-002 | Editar objetivo, público, ângulo, estrutura e CTA | MVP | Campos essenciais são editáveis e validados |
| EDIT-003 | Versionar e aprovar brief | MVP | Aprovar congela a versão; editar depois cria nova versão |
| EDIT-004 | Exportar brief | MVP | Exportação contém conteúdo, versão, fontes permitidas e data |
| EDIT-005 | Planejar no calendário | MVP | O usuário agenda, move e filtra itens por canal/status sem publicar automaticamente |
| EDIT-006 | Preservar histórico de decisões | MVP | Rejeição, edição e aprovação podem ser auditadas |

### 8.9 Produção DarkForge

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| PROD-001 | Enviar brief aprovado como intenção de produção | MVP condicionado | Só brief aprovado pode ser enviado; a intenção tem ID e versão |
| PROD-002 | Acompanhar produção e artifacts | MVP condicionado | A UI mostra estado real, etapas, erros e arquivos confirmados |
| PROD-003 | Pausar, retomar e cancelar quando suportado | MVP condicionado | A UI diferencia solicitação registrada de efeito confirmado |
| PROD-004 | Evitar duas fontes de verdade | MVP condicionado | Channel OS e executor não mantêm estados divergentes sem reconciliação |
| PROD-005 | Validar artifact final | MVP condicionado | Só artifact com manifest, checksum e estado `ready` aparece como concluído |

### 8.10 Jobs, erros e operação

| ID | Requisito | Prioridade | Critério de aceite |
|---|---|---|---|
| JOB-001 | Exibir fila e histórico | MVP | O usuário filtra por canal, tipo, estado e período |
| JOB-002 | Mostrar progresso baseado em etapas | MVP | Não há barra de progresso fictícia baseada apenas em tempo |
| JOB-003 | Pausar, retomar e cancelar | MVP | A ação informa se foi solicitada, aplicada ou recusada |
| JOB-004 | Recuperar após reinício | MVP | Jobs interrompidos são reconciliados sem duplicar efeitos |
| JOB-005 | Exibir erro acionável | MVP | Mensagem informa causa conhecida, retry possível e próxima ação |
| JOB-006 | Representar dependência indisponível | MVP | Rede, Supabase, quota e modelo podem gerar `BLOCKED/RECOVERABLE`, nunca sucesso |
| JOB-007 | Exportar diagnóstico seguro | P1 operacional | Pacote não contém tokens, cookies ou conteúdo sensível não autorizado |
| JOB-008 | Executar backup e restore | MVP operacional | Dados e arquivos são restaurados em ambiente isolado e validados |

---

## 9. Fluxos principais

### 9.1 Onboarding e primeiro valor

1. Usuário abre a aplicação local no navegador.
2. Autentica-se e entra no workspace.
3. Cria o primeiro Channel Profile ou seleciona um canal existente.
4. Define posicionamento, público, pilares e restrições mínimas.
5. Conecta o canal próprio por OAuth.
6. Inicia o sync incremental.
7. Acompanha etapas reais e eventuais dados indisponíveis.
8. Abre o dashboard com origem, período e frescor.
9. Recebe uma próxima ação sugerida: revisar perfil, pesquisar referências ou importar copies.

**Resultado esperado:** o usuário entende o estado do canal sem precisar interpretar uma tela cheia de números.

**Saídas alternativas:** OAuth negado, quota indisponível, Supabase fora do ar, canal sem métricas e sync parcial devem ter estados e próximos passos próprios.

### 9.2 Pesquisa até oportunidade

1. Usuário escolhe canal e objetivo editorial.
2. Define filtros e orçamento da pesquisa.
3. Revisa canais/vídeos candidatos e suas evidências.
4. Aprova referências relevantes e rejeita ruído.
5. Solicita análise de títulos/capas e geração de oportunidades.
6. Abre o painel “Por quê?” de uma oportunidade.
7. Inspeciona fontes, score, confiança, limitações e contexto RAG.
8. Edita, rejeita ou aprova a oportunidade.

**Resultado esperado:** uma decisão editorial rastreável, não apenas uma lista de ideias.

### 9.3 Oportunidade até brief

1. Usuário transforma oportunidade aprovada em brief.
2. Revisa objetivo, público, ângulo, estrutura, títulos e CTA.
3. Consulta as fontes e remove referências inadequadas.
4. Salva uma versão de rascunho.
5. Aprova explicitamente a versão.
6. Exporta ou agenda o item no calendário.

**Resultado esperado:** brief congelado, versionado e pronto para a próxima etapa.

### 9.4 Brief até produção

1. Usuário escolhe um brief aprovado.
2. Confirma a intenção de produção e os parâmetros permitidos.
3. O sistema cria um job idempotente.
4. O usuário acompanha etapas e artifacts.
5. Se necessário, solicita pausa ou cancelamento.
6. Em falha, consulta erro e retry recomendado.
7. Ao concluir, abre o artifact validado e o relatório de qualidade.

**Resultado esperado:** produção rastreável sem duas fontes de verdade nem falso sucesso.

### 9.5 Recuperação após falha

1. Aplicação ou worker é encerrado durante um job.
2. Ao retornar, o sistema reconcilia o estado pelo registro persistente.
3. O usuário vê `INTERRUPTED`, `RECOVERABLE` ou `BLOCKED`, conforme o caso.
4. O sistema valida checkpoint, lease e artifacts antes de retomar.
5. O retry não duplica fatos, uploads, gerações ou produções.
6. O usuário recebe confirmação somente após persistência do resultado.

---

## 10. Experiência e arquitetura de informação

### 10.1 Navegação principal

```text
Dashboard
├── Canais
│   ├── Visão geral
│   ├── Vídeos
│   ├── Analytics
│   ├── Perfil editorial
│   └── Referências
├── Pesquisa
│   ├── Canais semelhantes
│   ├── Vídeos e títulos
│   ├── Capas
│   └── Evidências
├── Oportunidades
├── Calendário
├── Briefs e Gerações
├── Knowledge / Copies
├── Produção DarkForge
├── Jobs e Qualidade
└── Configurações
```

### 10.2 Regras de UX

- O canal, workspace, período e versão editorial ativos ficam sempre identificáveis.
- Toda recomendação tem uma ação “Por quê?” ou equivalente.
- Toda métrica tem origem e atualização acessíveis sem sair do contexto.
- Jobs longos não bloqueiam a navegação.
- Ações destrutivas explicam impacto e possibilidade de reversão.
- Aprovação e rejeição são rápidas, mas não ambíguas.
- O usuário consegue inspecionar o contexto RAG sem ver segredos ou prompts internos sensíveis.
- O sistema diferencia conteúdo importado, inferência de IA e proposta criativa.
- O estado de rede e de persistência fica visível quando afeta a confiabilidade.

### 10.3 Estados obrigatórios de interface

Cada módulo deve ter estados para:

- carregamento inicial;
- vazio legítimo;
- sem permissão;
- dados parciais;
- dados desatualizados;
- erro recuperável;
- erro não recuperável;
- dependência externa indisponível;
- job em andamento;
- job pausado/cancelado/interrompido;
- sucesso confirmado.

### 10.4 Acessibilidade

- Navegação completa por teclado.
- Foco visível e ordem de foco previsível.
- Contraste adequado em temas claro e escuro.
- Labels e instruções para campos.
- Alternativa textual para análises visuais.
- Não depender apenas de cor para estados de métricas ou jobs.
- Mensagens de erro associadas ao campo/ação correspondente.
- Respeito a preferência de movimento reduzido.

---

## 11. Regras de negócio

### 11.1 Dados e métricas

1. Dados de canais próprios só entram após autorização válida.
2. Dados públicos de referências não são apresentados como analytics privados.
3. Métrica ausente nunca é convertida em zero.
4. Toda visão informa fonte, período e última atualização.
5. Dados parciais, tardios ou revisados mantêm seu estado e histórico.
6. Comparações precisam respeitar dimensões, granularidade e disponibilidade.
7. Uma falha parcial não apaga dados válidos já sincronizados.
8. O cursor e os fatos de uma unidade de sync são confirmados juntos.

### 11.2 Identidade editorial

1. Toda oportunidade pertence a um canal e a uma versão de Channel Profile.
2. Mudança de posicionamento não reescreve recomendações históricas.
3. Temas proibidos e restrições de direitos têm precedência sobre a geração.
4. Uma referência pode inspirar padrões, mas não autoriza cópia literal.
5. O usuário pode rejeitar uma sugestão sem precisar justificar, mas o motivo é incentivado para aprendizado.

### 11.3 IA e conhecimento

1. RAG é recuperação de contexto, não treinamento de pesos.
2. L0 não entra silenciosamente no contexto confiável.
3. Fonte arquivada não participa de novas gerações.
4. Toda geração registra modelo, versão de prompt, fontes e validações.
5. Conteúdo importado é dado não confiável, nunca instrução de sistema.
6. O sistema deve declarar quando não há contexto suficiente.
7. Fallback para provedor externo exige consentimento explícito.
8. O usuário deve saber quais categorias de dados serão enviadas a um provedor externo.
9. Nenhuma saída de IA pode aprovar brief ou iniciar produção por conta própria.

### 11.4 Aprovação e produção

1. Brief aprovado é uma versão congelada.
2. Editar um brief aprovado cria uma nova versão.
3. Somente brief aprovado pode virar intenção de produção.
4. Publicação automática não faz parte do MVP.
5. Um artifact só é considerado final depois de validação e manifest confirmado.
6. O Channel OS não altera estados internos do executor fora do contrato de integração.

---

## 12. Requisitos de dados e integrações

### 12.1 YouTube

- Usar APIs oficiais e escopos mínimos.
- Suportar OAuth, refresh, expiração e revogação.
- Respeitar quotas, políticas, limites de retenção e refresh das fontes.
- Manter orçamento de quota separado entre canais próprios e pesquisa pública.
- Registrar origem, revisão e disponibilidade de cada métrica.
- Não contornar autenticação, robots, restrições técnicas ou termos de uso.

### 12.2 Supabase

O Supabase é uma **dependência de implementação proposta**, não uma integração configurada nesta entrega.

Requisitos de produto associados:

- uma fonte de verdade durável para dados e estados;
- autenticação e isolamento por workspace;
- armazenamento privado de arquivos;
- busca lexical e vetorial com permissões;
- recuperação de jobs e consistência após falhas;
- backup e restore testáveis;
- comportamento explícito quando o serviço estiver indisponível.

A UI não deve receber credenciais privilegiadas. O usuário deve conseguir exportar seus dados e solicitar exclusão conforme a política definida.

### 12.3 Provedores de IA

- Modelos locais são preferenciais quando o hardware suportar.
- Provedores externos são opcionais e configuráveis.
- Não há fallback externo silencioso.
- Custos e limites devem ser visíveis por operação ou workspace.
- Dados sensíveis e segredos não entram em prompts desnecessariamente.
- A indisponibilidade de um modelo deve gerar estado recuperável, não conteúdo inventado.

### 12.4 DarkForge

- O pipeline de produção continua responsável por vídeos e artifacts.
- O Channel OS envia intenções e briefs versionados.
- Contratos de comando, progresso, cancelamento, recovery e artifact precisam ser confirmados no núcleo real.
- Qualquer persistência legada deve ter um único escritor por entidade.
- A integração não pode exigir que a UI chame FFmpeg ou manipule o banco diretamente.

---

## 13. Requisitos não funcionais

### 13.1 Segurança e privacidade

- Isolamento por workspace testado antes de dados reais.
- Sessões seguras, expiração e logout.
- Tokens OAuth criptografados e fora de logs.
- Nenhuma chave privilegiada no navegador.
- Validação de uploads, payloads, origem e destino de URLs.
- Proteção contra SSRF, CSRF, path traversal e prompt injection.
- Signed URLs ou proxy autorizado para arquivos privados.
- Diagnostics com redaction e revisão prévia.
- Exclusão cobrindo dados, embeddings, arquivos e caches, com retenção de backups informada.

### 13.2 Confiabilidade

- Nenhum falso sucesso.
- Nenhuma perda silenciosa de dados.
- Jobs com idempotência, retry, timeout e recovery.
- Reconciliação após reinício sem depender exclusivamente de abrir a UI.
- Eventos de progresso podem ser repetidos ou perdidos sem corromper o estado.
- Banco e arquivos têm manifests e reconciliação de inconsistências.
- Restore de dados e arquivos testado em ambiente isolado.

### 13.3 Performance e capacidade

Metas iniciais a validar no piloto:

- navegação entre telas já carregadas sem bloqueio perceptível;
- listas grandes paginadas ou virtualizadas;
- sync incremental sem varrer todo o histórico a cada execução;
- consultas de analytics por projeções/agregações adequadas;
- jobs longos fora do request da UI;
- limites de concorrência para IA, visão e workers;
- monitoramento de conexões, latência, Storage, egress e custo de embeddings.

### 13.4 Disponibilidade e modo degradado

- A aplicação informa quando não consegue alcançar a persistência remota.
- Cache local pode apoiar leitura, mas nunca é apresentado como dado confirmado.
- Sem conectividade, novas escritas ficam pendentes/bloqueadas conforme o contrato; não há conclusão falsa.
- O usuário recebe uma ação possível: tentar novamente, revisar conexão, aguardar quota ou exportar diagnóstico.

### 13.5 Compatibilidade e operação

- Interface principal no navegador.
- UI e workers executados no PC do usuário.
- EXE/launcher é opcional e futuro.
- Atualização não apaga dados sem confirmação específica.
- Logs e diagnóstico ajudam a localizar falhas sem expor segredos.

---

## 14. Telemetria de produto

A telemetria deve medir o fluxo sem coletar conteúdo editorial sensível por padrão.

### 14.1 Eventos mínimos

| Evento | Propriedades permitidas |
|---|---|
| `workspace.opened` | workspace anonimizado, versão da aplicação |
| `channel.connection.started` | plataforma, resultado, código de erro |
| `channel.sync.started` | tipo de sync, canal anonimizado |
| `channel.sync.completed` | duração, quantidade de itens, estado parcial/final |
| `research.started` | filtros agregados, orçamento, canal anonimizado |
| `research.completed` | duração, candidatos, quota consumida |
| `reference.curated` | decisão, tipo de referência |
| `knowledge.source.indexed` | tipo, nível de curadoria, quantidade de chunks |
| `opportunity.generated` | modelo, versão de prompt, quantidade |
| `opportunity.decided` | decisão, motivo agregado opcional |
| `brief.approved` | versão, tempo desde criação |
| `production.requested` | tipo de produção, versão do brief |
| `job.failed` | tipo, código de erro, retryable |
| `job.recovered` | tipo, duração da interrupção, resultado |
| `backup.restore.validated` | escopo, resultado, versão do schema |

### 14.2 Restrições

- Não enviar tokens, cookies, segredos ou copies completas.
- Não usar telemetria para reconstruir conteúdo privado sem necessidade.
- Permitir diagnóstico local sem envio externo.
- Separar métricas de produto de logs de segurança.

---

## 15. Dependências e premissas

### 15.1 Dependências externas

- Projeto Supabase de teste e, posteriormente, de produção.
- Conta e canal de teste autorizado no YouTube.
- Credenciais OAuth e políticas de quota válidas.
- Contratos reais do núcleo DarkForge.
- Hardware compatível com os modelos locais escolhidos, se essa opção for usada.
- Provedor externo de IA somente quando explicitamente configurado.

### 15.2 Premissas de produto

- YouTube é suficiente para validar o primeiro fluxo.
- O usuário aceita revisar recomendações e briefs.
- Existe pelo menos um conjunto inicial de copies ou referências para avaliar o RAG.
- O usuário possui direitos ou permissão para importar as fontes que cadastrar.
- O volume inicial não exige uma arquitetura distribuída de microserviços.
- O valor do produto está na decisão editorial, não na quantidade de agentes.

### 15.3 O que precisa ser comprovado antes do piloto

- Disponibilidade real das métricas necessárias.
- Custo e quota das pesquisas previstas.
- Qualidade mínima do retrieval e das citações.
- Capacidade de recuperar jobs sem duplicidade.
- Isolamento entre workspaces.
- Restore de dados e arquivos.
- Compatibilidade do executor DarkForge com o contrato proposto.

---

## 16. Roadmap de produto e gates

### Fase 0 — Fundações e validação

**Entrega:** PRD, arquitetura, ADRs, catálogo de métricas, políticas de fontes, protótipo navegável e conjunto inicial de avaliação.  
**Gate:** escopo do MVP aprovado, disponibilidade de dados conhecida e nenhuma regra crítica implícita.

### Fase 1 — Workspace e execução confiável

**Entrega:** autenticação, workspace, perfis, persistência, fila, logs, estados de erro e recovery.  
**Gate:** dois workspaces isolados; job real pode ser pausado, retomado, cancelado e recuperado; indisponibilidade não gera sucesso falso.

### Fase 2 — Canais e Analytics Center

**Entrega:** OAuth, catálogo, sync incremental/backfill, dashboards e ficha de vídeo.  
**Gate:** dados reais autorizados, origem/frescor visíveis, métricas ausentes corretas e histórico persistente.

### Fase 3 — Research Explorer

**Entrega:** pesquisa pública, candidatos semelhantes, evidências, curadoria e controle de quota.  
**Gate:** toda referência rastreável e nenhuma métrica privada inferida como fato.

### Fase 4 — Title e Thumbnail Intelligence

**Entrega:** análise de títulos, análise básica de capas, alternativas e checagem de similaridade.  
**Gate:** análise explicável, referências identificadas e nenhuma duplicidade exata apresentada como original.

### Fase 5 — Knowledge/RAG Studio

**Entrega:** importação, curadoria L0–L3, indexação, busca, citações e avaliação.  
**Gate:** fonte aprovada recuperada, fonte arquivada excluída e citações verificáveis.

### Fase 6 — Oportunidades e Editorial Studio

**Entrega:** score, oportunidades, feedback, briefs, versões, calendário e exportação.  
**Gate:** recomendação com evidências e limitações; aprovação congela a versão e preserva o histórico.

### Fase 7 — Produção DarkForge

**Entrega:** intenção de produção, acompanhamento, recovery e artifacts.  
**Gate:** produção real iniciada pela UI, progresso verdadeiro, output válido e uma única fonte de verdade.

### Fase 8 — Hardening e piloto

**Entrega:** backup/restore, diagnóstico, testes de segurança/rede/fila, instalação e launcher opcional.  
**Gate:** instalação limpa, upgrade sem perda, restore validado, isolamento comprovado e fluxo completo repetível.

---

## 17. Riscos de produto e resposta

| Risco | Sinal de alerta | Resposta de produto |
|---|---|---|
| Recomendações genéricas | Rejeição por “não tem relação com meu canal” | Reforçar perfil, evidências, filtros e curadoria antes de aumentar volume de IA |
| Usuário não confia nas métricas | Dúvidas sobre origem ou zeros inesperados | Mostrar semântica, frescor, disponibilidade e histórico |
| Pesquisa consome toda a quota | Sync próprio fica atrasado | Orçamento separado, prioridade e circuit breaker |
| RAG recupera conteúdo inadequado | Fontes antigas ou sem direitos aparecem | Curadoria, filtros, arquivamento e testes de exclusão |
| IA produz cópia ou promessa indevida | Similaridade alta ou alegações sem fonte | Checagem de originalidade, validação e aprovação humana |
| Custo de IA cresce | Reindexações e retries frequentes | Orçamento, deduplicação, cache permitido e limites por job |
| Falha de rede parece perda de dados | UI mostra vazio ou sucesso incorreto | Estado degradado explícito e recuperação orientada |
| Escopo trava o lançamento | Muitas plataformas/recursos em paralelo | Manter o caminho pesquisa → oportunidade → brief como prioridade |
| Integração DarkForge diverge | Estados diferentes entre UI e executor | Contrato único, single-writer e reconciliação |
| Usuário espera viralização | Frustração com resultados | Comunicar que o produto apoia decisões, não garante desempenho |

---

## 18. Questões abertas

Estas decisões precisam ser respondidas antes de fechar o piloto:

1. Quantos canais, vídeos e referências são esperados por workspace?
2. Quais idiomas e países precisam ser suportados no primeiro ciclo?
3. Qual é o hardware típico do PC do usuário?
4. Quais modelos locais são aceitáveis em qualidade, memória e velocidade?
5. Qual plano/região do Supabase atende aos limites de conexão, Storage, egress e recuperação?
6. Qual RPO/RTO e qual retenção de backups são necessários?
7. Qual orçamento mensal para banco, Storage, embeddings e IA?
8. É necessário apenas ler dados em modo degradado ou existe um requisito real de escrita offline?
9. Quais contratos já existem no núcleo DarkForge e há persistência legada a migrar?
10. Quais formatos de exportação são indispensáveis?
11. Qual política de retenção para raw payloads, thumbnails, transcrições e logs?
12. A publicação assistida deve entrar no roadmap imediatamente após o MVP?
13. Qual nome e identidade visual finais do produto?

---

## 19. Critérios de aceite do MVP

O MVP só pode ser considerado utilizável quando o fluxo abaixo for executado em instalação limpa, com projeto Supabase de teste e dois workspaces:

1. Autenticar e confirmar isolamento de dados, buscas e arquivos entre workspaces.
2. Criar/editar um perfil editorial e registrar uma mudança de tema.
3. Conectar um canal de teste autorizado.
4. Sincronizar canal, vídeos e métricas disponíveis.
5. Ver origem, período e última atualização em cada visão.
6. Confirmar que métricas indisponíveis não aparecem como zero.
7. Pesquisar canais semelhantes e aprovar referências.
8. Abrir evidências de títulos e capas sem confundir dado público com privado.
9. Importar copies, revisar, aprovar e indexar.
10. Gerar oportunidades e inspecionar score, fontes, limitações e contexto RAG.
11. Rejeitar uma sugestão, editar outra e aprovar uma terceira.
12. Criar brief e verificar que a aprovação congela a versão.
13. Exportar o brief e localizar suas fontes.
14. Iniciar uma produção DarkForge a partir do brief, se o contrato estiver disponível.
15. Acompanhar progresso real, pausar, retomar e cancelar em jobs distintos.
16. Fechar a aplicação durante um job e confirmar recuperação sem duplicar output.
17. Abrir o artifact final e o relatório de qualidade.
18. Provocar erro real e verificar mensagem, log e retry apropriado.
19. Derrubar a conectividade com o Supabase durante sync/upload e confirmar estado bloqueado/recuperável, sem sucesso falso.
20. Reiniciar e confirmar histórico, configurações e calendário.
21. Fazer backup de dados e arquivos, restaurar em projeto isolado e validar o resultado.

### 19.1 Gate absoluto

**Zero falso sucesso, zero perda silenciosa de dados, zero acesso indevido entre workspaces e nenhuma recomendação sem proveniência mínima.**

### 19.2 Definição de pronto para o piloto

- Requisitos MVP implementados ou explicitamente removidos do escopo.
- Testes de segurança, fila, rede, RAG e restore aprovados.
- Métricas de sucesso instrumentadas.
- Limitações conhecidas documentadas na interface.
- Fluxo de suporte/diagnóstico disponível.
- Nenhuma dependência crítica escondida em configuração manual.

---

## 20. Resultado esperado

O produto deve fechar este ciclo:

```text
DADOS AUTORIZADOS + REFERÊNCIAS PÚBLICAS + CONHECIMENTO CURADO
                              ↓
                 ANALYTICS + PESQUISA + RAG
                              ↓
          OPORTUNIDADES EXPLICÁVEIS E BRIEFS APROVADOS
                              ↓
                 PRODUÇÃO DARKFORGE RASTREÁVEL
                              ↓
             RESULTADOS E FEEDBACK PARA NOVAS ANÁLISES
```

O sucesso do DarkForge Channel OS não será medido pela quantidade de agentes, telas ou textos gerados. Será medido pela capacidade de ajudar o usuário a tomar uma decisão editorial melhor, entender por que ela foi tomada e executá-la sem perder dados, contexto ou controle.

---

## 21. Glossário

- **Channel Profile:** identidade editorial versionada de um canal.
- **Research Run:** execução de pesquisa com objetivo, filtros, fontes e resultados.
- **Referência:** canal, vídeo, título, capa ou outra fonte pública usada para análise.
- **Knowledge Source:** copy ou documento importado com origem, direitos e curadoria.
- **L0–L3:** níveis de curadoria que determinam o uso permitido no RAG.
- **RAG:** recuperação de contexto para condicionar uma geração, sem treinar pesos.
- **Oportunidade:** proposta de tema/episódio com evidências, score e limitações.
- **Brief:** documento editorial estruturado e versionado.
- **Artifact:** arquivo ou resultado de produção com manifest e validação.
- **Job:** unidade assíncrona de trabalho com estado, progresso e recovery.
- **Falso sucesso:** estado concluído sem resultado persistido e validado.
- **Workspace:** fronteira lógica de dados, canais, arquivos e permissões.
