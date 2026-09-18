from pulse.prompts.text_questionnaire import (
    extract_questionnaire_block,
    parse_text_questionnaire,
)

SAMPLE = """
Apresentando todas as perguntas agora:

```text
Preciso de algumas informações antes de continuar.

1. O que melhor descreve o Stock Trader?

A) Plataforma de paper trading — simular operações de bolsa sem dinheiro real
B) Sistema de gestão de portfólio com saldo virtual
C) Projeto full-stack de estudo e portfólio pessoal
D) Plataforma completa com potencial de produção futura
E) Outro (descreva)

2. Quem é o público-alvo e qual problema resolve?

A) Investidores iniciantes aprendendo a operar na bolsa
B) Desenvolvedores estudando arquitetura full-stack
C) Uso pessoal — simular investimentos sem risco
D) Público geral — praticar trading sem dinheiro real
E) Outro (descreva)

3. Qual é o foco da v1 neste momento?

A) Consolidar o que existe — fechar gaps, cobrir testes, estabilizar
B) Completar features pendentes (portfólio, transações, etc.)
C) Preparar para deploy em algum ambiente
D) Adicionar novas features (descreva quais)
E) Outro (descreva escopo e exclusões)

4. Há restrições críticas?

A) Sem prazo — evolução contínua local
B) Prazo definido (descreva)
C) Apenas ambiente local, sem deploy
D) Pretende colocar em produção em breve
E) Outro (descreva)

Resposta:
```
"""


def test_extract_questionnaire_block_from_fenced_text():
    block = extract_questionnaire_block(SAMPLE)
    assert block is not None
    assert "Stock Trader" in block
    assert "Resposta:" not in block


def test_parse_text_questionnaire_extracts_four_questions():
    parsed = parse_text_questionnaire(SAMPLE)
    assert parsed is not None
    assert len(parsed.questions) == 4
    assert parsed.questions[0].prompt.startswith("1.")
    assert len(parsed.questions[0].options) == 5
    assert parsed.questions[0].options[0] == (
        "A",
        "Plataforma de paper trading — simular operações de bolsa sem dinheiro real",
    )
