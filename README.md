# DarkForge Channel OS — documentação de produto e arquitetura

Este pacote contém **somente a documentação de produto e engenharia** para a ferramenta de gestão, pesquisa e inteligência editorial de canais. Nenhuma parte da ferramenta foi implementada.

## Documentos

- [PRD — requisitos de produto](docs/prd.md)
- [Arquitetura completa](docs/architecture.md)
- [Execução via IDE — plano mestre, subplanos e prompt geral](docs/execution/README.md)

## Decisão central

A proposta adapta o DarkForge descrito no material de referência para uma aplicação **local-controlled e cloud-backed, com interface no navegador**. UI e workers ficam no PC; o Supabase Postgres é a fonte de verdade, com Auth/RLS, pgvector e Storage privado. O núcleo de domínio, o Command Bus, o Job Manager, o Scheduler e os artifacts continuam sendo compartilhados por contratos explícitos. A interface web não chama FFmpeg, não usa credenciais privilegiadas e não duplica regras de negócio.

O EXE passa a ser uma opção futura de empacotamento/inicialização, não uma segunda aplicação.

## Escopo coberto

- Gestão de múltiplos canais e respectivas identidades editoriais.
- Sincronização de métricas de canais próprios autorizados.
- Pesquisa de canais e vídeos públicos semelhantes.
- Engenharia reversa de padrões de títulos e capas, com geração original.
- Analistas de canal, vídeo, audiência, concorrência, título, capa e copy.
- Base de conhecimento e RAG para copies, referências e aprendizados editoriais.
- Sugestão de temas e episódios com evidências, score e nível de confiança.
- Briefs, calendário editorial, aprovação humana e integração com produção.
- Fila Postgres com workers locais recuperáveis, logs, backups Postgres + Storage, RLS, segurança e testes.

## Premissas do desenho

1. YouTube é a primeira plataforma integrada; outras plataformas entram por adapters.
2. O uso inicial é de um único usuário em um PC, com vários canais no mesmo workspace; o isolamento por workspace e RLS já é obrigatório.
3. O Supabase precisa estar acessível para confirmar escritas e concluir jobs; cache local não é uma segunda fonte de verdade.
4. Canais próprios usam OAuth e APIs oficiais. Concorrentes fornecem somente dados públicos e permitidos.
5. O padrão é não publicar automaticamente: toda recomendação e produção passa por aprovação.
6. Modelos locais são preferenciais para privacidade; provedores externos são opcionais e nunca recebem fallback silencioso.
7. RAG significa recuperação de contexto com fontes versionadas, não treinamento dos pesos de um modelo.

## Ordem recomendada de leitura

1. PRD: visão, usuários, escopo, requisitos e métricas de sucesso.
2. Arquitetura: visão, limites e módulos funcionais.
3. Arquitetura de execução e persistência.
4. Modelo de dados e disponibilidade das métricas.
5. Pesquisa, analistas e motor de oportunidades.
6. RAG, proveniência e avaliação de IA.
7. APIs, jobs, segurança e operação.
8. Roadmap, gates e critérios de aceite.
9. Revisão crítica dos pontos de quebra e ordem segura de implementação.
10. Execução via IDE: plano mestre, subplanos, rastreabilidade e prompt geral.
