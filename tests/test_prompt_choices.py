from pulse.plan.quick_prompt import (
    classify_quick_questionnaire_outcome,
    first_questionnaire_answer,
)
from pulse.presentation.prompt.ask_question import (
    option_requires_description,
    is_other_option,
    should_add_other_option,
)
from pulse.presentation.prompt.handler import PromptHandler


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
        prompt="1. Este pedido excede o escopo do Quick mode. Como deseja prosseguir?",
        option_labels=[
            "Migrar para o pipeline completo (Specify → Design → Tasks → Execute)",
            "Quick fix: reutilizar TokenResponseAdapter no interceptor",
            "Quick fix: adicionar testes do RefreshTokenInterceptor",
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


def test_classify_quick_questionnaire_outcome():
    migration = (
        "Respostas coletadas via questionário interativo do Pulse:\n\n"
        "1. Como prosseguir?\n"
        "→ A) Migrar para o pipeline completo (Specify → Design → Tasks → Execute)\n"
    )
    reduce = (
        "Respostas coletadas via questionário interativo do Pulse:\n\n"
        "1. Como prosseguir?\n"
        "→ B) Quick fix: reutilizar TokenResponseAdapter no RefreshTokenInterceptor\n"
    )
    approve = (
        "Respostas coletadas via questionário interativo do Pulse:\n\n"
        "1. Aprovar?\n"
        "→ A) Sim, aprovar e implementar\n"
    )

    assert classify_quick_questionnaire_outcome(migration) == "migrate"
    assert classify_quick_questionnaire_outcome(reduce) == "reduce_scope"
    assert classify_quick_questionnaire_outcome(approve) == "approve"
    assert classify_quick_questionnaire_outcome("→ C) Cancelar") == "cancel"


def test_first_questionnaire_answer():
    text = "foo\n→ B) Quick fix: testes\nbar"
    assert first_questionnaire_answer(text) == "B) Quick fix: testes"


def test_handler_format_answer_with_follow_up_detail():
    from pulse.presentation.prompt.text_questionnaire import TextQuestion

    handler = PromptHandler()
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
    handler = PromptHandler()
    options = [
        {"id": "A", "label": "Migrar para o pipeline completo"},
        {"id": "B", "label": "Quick fix: reutilizar adapter"},
        {"id": "C", "label": "Cancelar"},
    ]
    choices = handler._build_choices(
        options,
        prompt="1. Este pedido excede o escopo do Quick mode. Como deseja prosseguir?",
    )
    assert len(choices) == 3
    assert all(str(choice.value) != "__other__" for choice in choices)


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
    handler = PromptHandler()
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
    other_choices = [choice for choice in choices if str(choice.value) == "__other__"]
    assert len(other_choices) == 1
    assert sum("Outro" in str(choice.title) for choice in choices) == 1


def test_textual_build_choices_does_not_duplicate_existing_other():
    from pulse.tui.adapters.prompt_bridge import PromptBridge, TextualPromptHandler

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
    handler = PromptHandler()
    options = [
        {"id": "A", "label": "Paper trading"},
        {"id": "B", "label": "Gestão de portfólio"},
    ]
    choices = handler._build_choices(options, prompt="1. O que você está construindo?")
    assert any(str(choice.value) == "__other__" for choice in choices)
