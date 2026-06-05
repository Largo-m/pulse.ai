# Protocolo de perguntas técnicas

Protocolo estruturado de clarificação técnica para criação de TechSpec. Siga estas fases e regras para conduzir a conversa do PRD ao documento técnico.

## Fases

### 1. Contexto

Reúna contexto técnico antes de perguntar.
- Leia o PRD, ADRs existentes e explore o repositório alvo.
- Identifique padrões arquiteturais, stack, integrações e limites do código.

### 2. Clarificação técnica

Aprofunde decisões de implementação com o usuário.
- COMO implementar cada capacidade do PRD?
- ONDE os componentes devem viver no repositório?
- QUAIS tecnologias, padrões ou bibliotecas usar ou evitar?
- Quais são os requisitos de testes, desempenho e observabilidade?
- Quais integrações externas são necessárias?

### 3. Decisões

Registre decisões técnicas significativas em ADRs.
- Documente a abordagem escolhida e alternativas rejeitadas.
- Crie um ADR por decisão relevante (arquitetura, dados, APIs, integrações).

### 4. Rascunho

Gere a TechSpec com base nas respostas confirmadas.
- Preencha o template canônico.
- Itens ainda incertos vão para a seção de riscos ou perguntas em aberto.

### 5. Revisão

Apresente o rascunho completo para aprovação do usuário.
- Itere até aprovação explícita antes de salvar o arquivo final.

## Regras

### Ferramenta interativa de perguntas
- Toda pergunta DEVE ser feita com a ferramenta interativa do runtime — aquela que apresenta a pergunta e pausa a execução até o usuário responder.
- Não emita perguntas como texto corrido e continue gerando.
- Se a ferramenta não existir, apresente a pergunta como mensagem completa e pare de gerar.

### Limites de perguntas
- Faça apenas uma pergunta por mensagem. Se o tema exigir mais profundidade, divida em sequência de perguntas individuais.
- Prefira perguntas de múltipla escolha (A, B, C, D) quando as opções puderem ser predeterminadas.
- Inclua opção de fallback (ex.: "D) Outro — descreva").
- Aguarde a resposta antes da próxima pergunta.
- Faça entre 3 e 6 perguntas técnicas antes de redigir a TechSpec.

### Portões de progressão
- Conclua a exploração do código antes de iniciar as perguntas.
- Conclua pelo menos uma rodada completa de clarificação técnica antes de criar ADRs e redigir a TechSpec.
- Não salve `_techspec.md` até o usuário aprovar o rascunho final.

### Limites de foco
- Perguntas devem focar em COMO, ONDE e QUAIS (implementação).
- Nunca pergunte O QUÊ, POR QUÊ ou PARA QUEM — isso pertence ao PRD.
- Evite reabrir decisões de produto já fechadas no PRD, salvo conflito técnico explícito.

### YAGNI
- Remova componentes, abstrações e integrações desnecessárias durante a clarificação.
- Prefira estender código existente a criar novas camadas.
- Adie complexidade não essencial para fases futuras.

### Anti-padrão: pular clarificação por simplicidade
Toda TechSpec passa pelo protocolo completo de perguntas, independentemente da simplicidade aparente. Mudanças "simples" são onde premissas arquiteturais não examinadas causam mais falhas de integração.
