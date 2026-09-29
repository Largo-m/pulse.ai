from pulse.prompts.approval import classify_outcome, picked_answers
from pulse.prompts.ask_question import (
    is_other_option,
    option_requires_description,
    should_add_other_option,
)
from pulse.prompts.text_questionnaire import TextQuestion
from pulse.tui.adapters.prompt_bridge import PromptBridge, TextualPromptHandler


def test_option_requires_description():
    assert option_requires_description("B) Não, preciso de ajustes (descreva abaixo)")
    assert option_requires_description("Reduzir escopo (descreva o recorte)")
    assert not option_requires_description("B) Quick fix: reutilizar TokenResponseAdapter")


def test_should_add_other_option_open_questionnaire():
    assert should_add_other_option(
        prompt="1. O que você está construindo?",
        option_labels=[
            "Plataforma de paper trading",
            "Sistema de gestão de portfólio",
        ],
    )


def test_should_not_add_other_option_migration_gate():
    assert not should_add_other_option(
        prompt="1. Este pedido excede o escopo do step. Como deseja prosseguir?",
        option_labels=[
            "Reduzir o escopo para caber neste step",
            "Reutilizar o TokenResponseAdapter no interceptor",
            "Adicionar testes do RefreshTokenInterceptor",
            "Cancelar",
        ],
    )


def test_should_not_add_other_option_approval_gate():
    assert not should_add_other_option(
        prompt="1. Aprovar quick task 001 e implementar?",
        option_labels=[
            "Sim, aprovar e implementar",
            "Não, preciso de ajustes (descreva abaixo)",
        ],
    )


def test_classify_outcome_reads_the_approval_questionnaire():
    def answers(text: str) -> str:
        return (
            "Respostas coletadas via questionário interativo do Pulse:\n\n"
            "1. Aprovar?\n"
            f"→ {text}\n"
        )

    assert classify_outcome(answers("A) Sim, aprovar e seguir")) == "approve"
    assert classify_outcome(answers("B) Não, preciso de ajustes")) == "adjust"
    assert classify_outcome(answers("C) Pular este step")) == "skip"
    assert classify_outcome(answers("D) Cancelar")) == "cancel"
    assert classify_outcome("sem resposta nenhuma") == "unknown"


def test_free_text_guidance_never_approves():
    """"Revise o fluxo de aprovação" é orientação, não um "sim"."""
    answers = "1. Aprovar?\n→ Outro — revise o fluxo de aprovação do checkout\n"
    assert classify_outcome(answers) != "approve"


def test_picked_answers_reads_only_the_arrow_lines():
    text = "foo\n→ B) Quick fix: testes\nbar"
    assert picked_answers(text) == ["B) Quick fix: testes"]


def test_handler_format_answer_with_follow_up_detail():
    handler = TextualPromptHandler(PromptBridge())
    question = TextQuestion(
        id="q1",
        prompt="1. Ajustes?",
        options=(("B", "Não, preciso de ajustes (descreva abaixo)"),),
    )
    formatted = handler._format_answer(
        question,
        {"selectedOptionIds": ["B::Incluir testes do interceptor"]},
    )
    assert formatted == "B) Não, preciso de ajustes (descreva abaixo) — Incluir testes do interceptor"


def test_build_choices_suppresses_other_for_migration():
    handler = TextualPromptHandler(PromptBridge())
    options = [
        {"id": "A", "label": "Reduzir o escopo"},
        {"id": "B", "label": "Reutilizar o adapter"},
        {"id": "C", "label": "Cancelar"},
    ]
    choices = handler._build_choices(
        options,
        prompt="1. Este pedido excede o escopo do step. Como deseja prosseguir?",
    )
    assert len(choices) == 3
    assert all(choice[0] != "__other__" for choice in choices)


def test_is_other_option_detects_describe_variants():
    assert is_other_option("E", "Outro (descreva)")
    assert is_other_option("E", "E) Outro (descreva)")
    assert is_other_option("", "Outro")
    assert is_other_option("other", "Something")
    assert is_other_option("__other__", "x")
    assert not is_other_option("A", "Produto / plataforma com usuários")
    assert not is_other_option("B", "Não, preciso de ajustes (descreva abaixo)")


def test_should_not_add_other_when_label_already_exists():
    assert not should_add_other_option(
        prompt="1. O que você está construindo?",
        option_labels=[
            "Produto / plataforma com usuários",
            "API / serviço backend",
            "Outro (descreva)",
        ],
    )


def test_build_choices_does_not_duplicate_existing_other():
    handler = TextualPromptHandler(PromptBridge())
    options = [
        {"id": "A", "label": "Produto / plataforma com usuários"},
        {"id": "B", "label": "API / serviço backend"},
        {"id": "C", "label": "Biblioteca / pacote interno"},
        {"id": "D", "label": "Automação / script / CLI"},
        {"id": "E", "label": "Outro (descreva)"},
    ]
    choices = handler._build_choices(
        options,
        prompt="1. O que você está construindo?",
    )
    other_choices = [choice for choice in choices if choice[0] == "__other__"]
    assert len(other_choices) == 1
    assert sum("Outro" in label for _, label in choices) == 1


def test_textual_build_choices_does_not_duplicate_existing_other():
    handler = TextualPromptHandler(PromptBridge())
    options = [
        {"id": "A", "label": "Produto / plataforma com usuários"},
        {"id": "E", "label": "Outro (descreva)"},
    ]
    choices = handler._build_choices(
        options,
        prompt="1. O que você está construindo?",
    )
    other_choices = [choice for choice in choices if choice[0] == "__other__"]
    assert len(other_choices) == 1
    assert sum("Outro" in label for _, label in choices) == 1


def test_build_choices_adds_other_for_open_questions():
    handler = TextualPromptHandler(PromptBridge())
    options = [
        {"id": "A", "label": "Paper trading"},
        {"id": "B", "label": "Gestão de portfólio"},
    ]
    choices = handler._build_choices(options, prompt="1. O que você está construindo?")
    assert any(choice[0] == "__other__" for choice in choices)
