# Sede DarkForge: todos os canais num prédio só

Uma visão geral em 3D onde **cada canal é um estúdio** (uma sala) dentro de um prédio.
O nome do canal fica **do lado de fora**, num letreiro iluminado em cima da porta, e os
bonequinhos dos agentes de cada canal trabalham lá dentro, em tempo real.

O escritório 3D atual (`components/studio/office3d/`) continua existindo: ele vira o
"interior detalhado" de um estúdio. A Sede é o andar de cima na hierarquia:

```
Sede (todos os canais)  ──clicar num estúdio──▶  Foco no estúdio  ──"Entrar"──▶  Escritório do canal (atual)
        ▲                                                                              │
        └──────────────────────────────── "Voltar para a Sede" ◀──────────────────────┘
```

## Arquivos

| Arquivo | Para que serve |
| --- | --- |
| `plan.md` | Plano mestre: objetivo, decisões, arquitetura, fluxo, ordem e gates |
| `design-spec.md` | Direção de arte completa (o "designer"): materiais, luz, cores, letreiros, bonecos, câmera, estados |
| `subplans/HQ-00` a `HQ-07` | Subplanos com tarefas, arquivos, testes e gate de cada etapa |
| `prompts.md` | Prompt geral + 1 prompt por subplano, prontos para colar na IA |
| `reference/sede-conceito.png` | Imagem conceito (referência de clima, não de pixels; os nomes vêm dos dados) |

## Como usar

1. Copie a pasta `docs/studio-hq/` para dentro do repositório `darkforge`, em `docs/studio-hq/`.
2. Abra `prompts.md`, cole o **Prompt geral** na IA uma vez.
3. Depois cole os prompts **HQ-00, HQ-01, ... HQ-07 em ordem**, um por vez. Só passe para o
   próximo quando a IA mostrar o gate do anterior marcado e as checagens passando.
4. No fim de cada subplano a IA faz 1 commit numa branch `feat/sede-canais` e atualiza
   `docs/studio-hq/state.md`.

## Ordem e dependências

```
HQ-00 Contratos ─┬─▶ HQ-01 Dados agregados (backend) ───────────────┐
                 └─▶ HQ-02 Layout do prédio ─▶ HQ-03 Módulo estúdio ─┼─▶ HQ-05 Câmera e navegação ─▶ HQ-06 HUD e acessibilidade ─▶ HQ-07 Gate visual
                                               HQ-04 Bonecos em massa ┘
```

HQ-01 (backend) e HQ-02/03/04 (cena) podem andar em paralelo depois do HQ-00.
