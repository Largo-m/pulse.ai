# Modelo de PRD

Use este modelo para estruturar todo Documento de Requisitos de Produto. Preencha cada seção com base nos resultados do brainstorming. Deixe orientações de placeholder nas seções com informação insuficiente e registre-as em Perguntas em aberto.

O título H1 do documento salvo DEVE ser `# PRD: [Nome da feature em português (Brasil)]`.

## Visão geral

Visão de alto nível da feature ou produto. Descreva:
- Qual problema resolve
- Para quem é
- Por que é valioso

## Objetivos

Objetivos específicos e mensuráveis desta feature ou produto:
- Métricas de sucesso e indicadores-chave de desempenho
- Objetivos de negócio e resultados esperados
- Prazos ou marcos alvo

## Histórias de usuário

Histórias de usuário organizadas por persona:
- Como [tipo de usuário], quero [ação] para [benefício]
- Personas principais e seus fluxos principais
- Personas secundárias e casos extremos

## Funcionalidades principais

Funcionalidades principais agrupadas por prioridade:
- Nome da funcionalidade: o que faz, por que é importante, comportamento em alto nível
- Requisitos funcionais de cada funcionalidade
- Interação entre funcionalidades

## Experiência do usuário

Jornada do usuário do primeiro contato ao uso regular:
- Personas-chave e seus objetivos
- Fluxos principais passo a passo
- Considerações de UI/UX e requisitos de acessibilidade
- Onboarding e descoberta

## Restrições técnicas em alto nível

Limites necessários que moldam o produto sem prescrever implementação:
- Integrações obrigatórias com sistemas existentes
- Mandatos de conformidade ou requisitos regulatórios
- Metas de desempenho na perspectiva do usuário
- Requisitos de privacidade e segurança de dados

NÃO inclua detalhes de implementação como bancos de dados específicos, frameworks, designs de API ou padrões de arquitetura.

## Fora de escopo

Funcionalidades explicitamente excluídas e limites:
- Funcionalidades intencionalmente adiadas para fases futuras
- Problemas adjacentes que não serão abordados
- Limites deste esforço

## Plano de entrega por fases

Plano de entrega incremental com critérios de sucesso por fase:

### MVP (Fase 1)
- Funcionalidades principais incluídas
- Critérios de sucesso para avançar à Fase 2

### Fase 2
- Funcionalidades adicionais
- Critérios de sucesso para avançar à Fase 3

### Fase 3
- Conjunto completo de funcionalidades
- Critérios de sucesso de longo prazo

## Métricas de sucesso

Medidas quantificáveis de sucesso:
- Métricas de engajamento do usuário
- Benchmarks de desempenho na perspectiva do usuário
- Indicadores de impacto no negócio
- Atributos de qualidade

## Riscos e mitigações

Riscos não técnicos que podem afetar o produto:
- Riscos de adoção e estratégias de mitigação
- Riscos competitivos
- Restrições de prazo e recursos
- Riscos de dependência de fatores externos

NÃO inclua riscos técnicos como complexidade arquitetural ou dívida técnica.

## Registros de decisão de arquitetura

ADRs que documentam decisões-chave feitas durante o brainstorming:
- [ADR-NNN: Título em português](adrs/adr-NNN.md) — Resumo em uma linha da decisão

## Perguntas em aberto

Itens pendentes que precisam de esclarecimento:
- Requisitos pouco claros
- Casos extremos que exigem input das partes interessadas
- Dependências de decisões ainda não tomadas
