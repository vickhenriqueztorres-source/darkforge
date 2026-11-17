# SP-06 — Knowledge/RAG Studio

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-01 e SP-02; integra referências de SP-04/05  
**Desbloqueia:** SP-07  
**Objetivo:** transformar copies e fontes curadas em contexto recuperável, autorizado, citável e reconstruível.

## 1. Escopo

Importação, metadados, direitos, curadoria L0–L3, deduplicação, chunks, embeddings versionados, FTS/pgvector, filtros, citações, arquivamento, exclusão e avaliação.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-06-T01 | Implementar importação de fontes | Texto/arquivos permitidos, metadados e validação | Tipo, canal, idioma, origem, direitos e contexto são registrados |
| SP-06-T02 | Implementar curadoria L0–L3 | Revisão, status, coleções e permissões de uso | Usuário entende cada nível; L0 não entra por padrão no contexto confiável |
| SP-06-T03 | Implementar deduplicação e versionamento | Hash, versões e histórico de reimportação | Reimportar não duplica silenciosamente nem apaga histórico |
| SP-06-T04 | Implementar chunking | Chunks com posição, versão e referência à fonte | Cada chunk pode ser rastreado até a fonte e ao workspace/canal |
| SP-06-T05 | Implementar EmbeddingRevision | Modelo, dimensão, versão, status e rebuild | Troca de modelo não mistura vetores incompatíveis; rebuild é isolado e retomável |
| SP-06-T06 | Implementar busca híbrida | FTS/trgm + pgvector e filtros autorizados | Workspace, canal, idioma, status e direitos são aplicados antes do contexto |
| SP-06-T07 | Implementar contexto e citações | Retrieval para geração e painel de fontes | Usuário abre os chunks/fontes usados; chunk IDs são validados após a busca |
| SP-06-T08 | Implementar arquivamento e exclusão | Remoção de índice, chunks, embeddings, caches e objetos | Fonte arquivada não aparece em novas buscas; exclusão cobre derivados |
| SP-06-T09 | Implementar Provider Router seguro | Modelo local/externo, consentimento e orçamento | Não há fallback externo silencioso; dados enviados e custo são identificados |
| SP-06-T10 | Construir Knowledge Studio UI | Importar, revisar, indexar, buscar, citar e excluir | Estados de indexação/erro são reais e ações têm confirmação |
| SP-06-T11 | Criar avaliação de retrieval | T-RAG-001/002, T-AI-001 e golden dataset | Recall, precisão de citação, arquivamento, rebuild e prompt injection são testados |

## 3. Regras de segurança e qualidade

- Conteúdo importado é dado não confiável, nunca instrução de sistema.
- RLS/filtros não podem ser aplicados somente depois que o conteúdo já foi enviado ao modelo.
- Fonte sem direitos ou fora do escopo não entra no contexto.
- Embeddings são projeções reconstruíveis, não uma segunda fonte de verdade.
- Reindexação e retries têm deduplicação por hash e orçamento.
- Uma geração antiga preserva as fontes/versões que usou, mesmo se a fonte for arquivada depois, conforme a política de retenção.

## 4. Testes mínimos

- Importação duplicada, fonte vazia, encoding inválido e arquivo grande.
- L0, L1, L2 e L3 com permissões diferentes.
- Busca cruzada por workspace/canal/idioma/direitos.
- Fonte arquivada e excluída após indexação.
- Troca de modelo/dimensão e rebuild interrompido.
- Citação inexistente ou chunk de outro workspace.
- Prompt injection dentro de copy.
- Provedor externo indisponível e fallback não autorizado.

## 5. Gate G6

Só avançar quando:

- fonte aprovada é recuperada corretamente;
- fonte arquivada/excluída não participa de novas buscas;
- citações são verificáveis;
- embeddings têm revisão e rebuild;
- provedor externo não recebe dados sem consentimento;
- KNOW-001–008 e ADR-006/007/009/010 têm evidência.
