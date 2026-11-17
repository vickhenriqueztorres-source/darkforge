# SP-05 — Title e Thumbnail Intelligence

**Estado inicial:** NOT_STARTED  
**Depende de:** SP-04  
**Desbloqueia:** SP-07  
**Objetivo:** analisar padrões de títulos e capas e gerar alternativas originais, explicáveis e revisáveis.

## 1. Escopo

Análise estrutural de títulos, geração de alternativas, OCR/visão de capas quando disponível, comparação de padrões, checagem de similaridade e interface de evidências.

## 2. Tarefas

| ID | Tarefa | Entrega | Critério de aceite |
|---|---|---|---|
| SP-05-T01 | Implementar analisador de títulos | Features estruturais e schema de análise | Promessa, especificidade, formato, gancho e outros padrões têm exemplos e confiança |
| SP-05-T02 | Implementar gerador de títulos | Alternativas ligadas a canal, objetivo e referências | Cada alternativa mostra diferenciação e não copia literalmente a referência |
| SP-05-T03 | Implementar ingestão de capas | Download permitido, metadados, hash e retenção | Imagem tem origem e política de armazenamento; falha não vira capa fictícia |
| SP-05-T04 | Implementar OCR/visão opcional | Texto, composição e elementos detectados | Resultado é identificado como análise probabilística; indisponibilidade é explícita |
| SP-05-T05 | Implementar comparação visual | Padrões comuns e direção diferenciada | O sistema aponta semelhanças sem recomendar reprodução |
| SP-05-T06 | Implementar checagem de originalidade | Similaridade textual/visual e revisão | Resultados muito próximos são sinalizados antes de aprovação |
| SP-05-T07 | Construir UI de análise | Referências, análise, alternativas e motivos | Usuário distingue observação, inferência e proposta criativa |
| SP-05-T08 | Criar golden tests de títulos/capas | Casos esperados, cópia, promessa sem evidência e poucos dados | TITLE/THUMB/ORIG têm avaliação repetível e limitações documentadas |

## 3. Regras de IA e direitos

- Não apresentar OCR ou visão como verdade absoluta.
- Não gerar uma capa final como se fosse artifact de produção no MVP.
- Não usar referência para reproduzir texto, layout ou identidade de outro canal.
- Se o modelo de visão não estiver disponível, manter o fluxo de títulos e marcar a análise visual como indisponível.
- Registrar modelo, prompt, versão e referências usadas em cada geração.

## 4. Testes mínimos

- Títulos com padrões conhecidos e títulos ambíguos.
- Alternativa idêntica ou quase idêntica à referência.
- Capa sem texto, imagem quebrada e OCR indisponível.
- Prompt injection embutido em texto de referência.
- Canal com poucos dados e canal com restrições editoriais.
- Fonte arquivada depois de uma análise histórica.

## 5. Gate G5

Só avançar quando:

- análises são explicáveis e têm referências;
- alternativas são originais e revisáveis;
- indisponibilidade de visão não gera invenção;
- similaridade indevida é sinalizada;
- TITLE-001/002, THUMB-001–003 e ORIG-001 têm evidência.
