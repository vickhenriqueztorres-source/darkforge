# SP-01 — Workspace, Auth e fundação de dados

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-00  
**Desbloqueia:** SP-02 e a base de SP-06  
**Objetivo:** criar o shell da aplicação e uma fronteira segura de workspace antes de importar dados reais.

## 1. Escopo

Next.js/React no navegador, serviços de aplicação, Supabase Postgres/Auth, memberships, RLS, migrations, workspaces, canais e Channel Profiles versionados. O EXE não é uma segunda aplicação.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-01-T01 | Confirmar topologia e configuração | Estrutura de app, workers e pacotes alinhada ao repositório | Não foi criada arquitetura paralela; comandos de desenvolvimento e testes funcionam |
| SP-01-T02 | Criar migrations base | Workspaces, memberships, canais, perfis, versões e campos de auditoria | Migrations são repetíveis, versionadas e têm chaves/índices adequados |
| SP-01-T03 | Integrar Supabase Auth | Sessão, login/logout, expiração e tratamento de callback | Usuário não autenticado não acessa dados; sessão não é confundida com OAuth YouTube |
| SP-01-T04 | Implementar memberships e contexto de workspace | Seleção de workspace e escopo obrigatório nos serviços | Toda operação recebe/resolve workspace autorizado; IDs não são confiáveis sem membership |
| SP-01-T05 | Escrever policies RLS | Policies por tabela/operação e testes de isolamento | Dois usuários/workspaces não veem nem alteram dados cruzados; vazio e erro são distintos |
| SP-01-T06 | Implementar Channel Profile | CRUD, público, voz, pilares, formatos, restrições e idioma | Perfil pode ser criado/editado e validado para vários canais no mesmo workspace |
| SP-01-T07 | Versionar perfil e mudanças editoriais | ProfileVersion e histórico de tema/posicionamento | Edição cria versão; recomendações antigas continuam ligadas à versão original |
| SP-01-T08 | Criar serviços de aplicação e API local | Comandos/consultas com validação e erros tipados | UI não executa SQL privilegiado nem duplica regras; respostas têm contrato |
| SP-01-T09 | Construir shell e navegação | Dashboard inicial, seleção de workspace/canal e páginas base | Canal/workspace ativos ficam visíveis; navegação é responsiva e acessível |
| SP-01-T10 | Implementar estados de interface | Loading, vazio, sem permissão, erro, parcial e offline | Nenhum erro aparece como “sem dados”; ações de retry são claras |
| SP-01-T11 | Configurar variáveis e exemplo seguro | `.env.example`, validação de configuração e documentação | Nenhum segredo real é commitado; service role nunca vai ao navegador |
| SP-01-T12 | Executar gate de segurança inicial | Testes automatizados e evidência | T-SEC-001/002 passam antes de qualquer importação real |

## 3. Regras de implementação

- RLS não é substituída por filtros apenas na UI.
- Backend privilegiado deve ter escopo explícito e grants mínimos.
- RPCs `security definer` precisam de allowlist, `search_path` fixo e validação de membership.
- O usuário pode ter vários canais em um workspace; não criar um workspace por canal.
- O perfil editorial é versionado independentemente do catálogo de vídeos.
- A UI deve ser capaz de mostrar o último estado carregado sem chamá-lo de dado confirmado quando a persistência estiver indisponível.

## 4. Testes mínimos

- Login, logout, sessão expirada e callback inválido.
- Usuário sem membership tentando acessar workspace por ID.
- Dois workspaces com canais, perfis e versões semelhantes.
- Consultas diretas, RPCs, APIs e arquivos com IDs cruzados.
- Perfil editado após uma recomendação histórica.
- Erro de banco versus workspace vazio.
- Teclado, foco, labels e contraste do shell.

## 5. Gate G1

Só avançar quando:

- app abre no navegador e autentica;
- dois workspaces estão comprovadamente isolados;
- perfil e versões persistem;
- nenhum dado real foi importado antes das policies;
- erros e estados degradados são compreensíveis;
- a matriz AUTH/CH-001–004 está com evidência.
