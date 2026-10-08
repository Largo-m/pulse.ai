import pytest

from pulse.replies.acp_payloads import QuestionAnswer, QuestionOption
from pulse.replies.approval import (
    answer_needs_description,
    classify_outcome,
    picked_answers,
)
from pulse.replies.ask_question import (
    build_question_choices,
    is_other_option,
    option_requires_description,
    should_add_other_option,
)
from pulse.replies.text_questionnaire import TextQuestion
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
            f"Respostas coletadas via questionário interativo do Pulse:\n\n1. Aprovar?\n→ {text}\n"
        )

    assert classify_outcome(answers("A) Sim, aprovar e seguir")) == "approve"
    assert classify_outcome(answers("B) Não, preciso de ajustes")) == "adjust"
    assert classify_outcome(answers("C) Pular este step")) == "skip"
    assert classify_outcome(answers("D) Cancelar")) == "cancel"
    assert classify_outcome("sem resposta nenhuma") == "unknown"


def test_free_text_guidance_never_approves():
    """Guidance like "Revise o fluxo de aprovação" is not a "yes"."""
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
        QuestionAnswer("q1", ("B::Incluir testes do interceptor",)),
    )
    assert (
        formatted == "B) Não, preciso de ajustes (descreva abaixo) — Incluir testes do interceptor"
    )


def test_build_choices_suppresses_other_for_migration():
    options = [
        QuestionOption("A", "Reduzir o escopo"),
        QuestionOption("B", "Reutilizar o adapter"),
        QuestionOption("C", "Cancelar"),
    ]
    choices = build_question_choices(
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
    options = [
        QuestionOption("A", "Produto / plataforma com usuários"),
        QuestionOption("B", "API / serviço backend"),
        QuestionOption("C", "Biblioteca / pacote interno"),
        QuestionOption("D", "Automação / script / CLI"),
        QuestionOption("E", "Outro (descreva)"),
    ]
    choices = build_question_choices(
        options,
        prompt="1. O que você está construindo?",
    )
    other_choices = [choice for choice in choices if choice[0] == "__other__"]
    assert len(other_choices) == 1
    assert sum("Outro" in label for _, label in choices) == 1


def test_textual_build_choices_does_not_duplicate_existing_other():
    options = [
        QuestionOption("A", "Produto / plataforma com usuários"),
        QuestionOption("E", "Outro (descreva)"),
    ]
    choices = build_question_choices(
        options,
        prompt="1. O que você está construindo?",
    )
    other_choices = [choice for choice in choices if choice[0] == "__other__"]
    assert len(other_choices) == 1
    assert sum("Outro" in label for _, label in choices) == 1


def test_build_choices_adds_other_for_open_questions():
    options = [
        QuestionOption("A", "Paper trading"),
        QuestionOption("B", "Gestão de portfólio"),
    ]
    choices = build_question_choices(options, prompt="1. O que você está construindo?")
    assert any(choice[0] == "__other__" for choice in choices)


def test_the_field_opens_for_any_way_of_asking_for_text():
    """The agent paraphrases and translates: matching a literal `(descreva)` was not enough."""
    for label in (
        "B) Não, preciso de ajustes (descreva)",
        "B) Não, preciso de ajustes (descreva abaixo)",
        "B) [Cenário A — descreva]",
        "B) No, I need changes (describe)",
        "B) Não — especifique o que mudar",
        "B) Não, preciso de ajustes. Descreva:",
        "C) Outro (describe your case)",
        "D) Reduzir escopo (descreva o recorte)",
    ):
        assert option_requires_description(label), label


def test_the_field_does_not_open_for_a_label_that_only_mentions_the_verb():
    """A request to the user comes in parentheses, brackets or a tail, not loose mid-sentence."""
    for label in (
        "A) Sim, aprovar e continuar",
        "C) Cancelar workflow",
        "B) A documentação que descreve o fluxo está correta",
        "B) Quick fix: reutilizar TokenResponseAdapter",
        "A) Sim: busca no título e na descrição; o trecho fica em negrito nos dois",
        "A) Sim: a tarefa aparece se cada palavra estiver no título OU na descrição",
        "B) Não (só o título, a descrição fica de fora)",
    ):
        assert not option_requires_description(label), label


def test_in_an_approval_gate_every_no_opens_the_field():
    """The guarantee that does not depend on the agent's wording.

    Approve, skip and cancel are self-explanatory. Everything else goes back to the
    agent as "the user wants changes"; without text, it redoes the step blindly.
    """
    prompt = "1. Aprovar Techspec e avançar?"
    for label in ("B) Não, preciso de ajustes", "B) Não", "B) No, I need changes"):
        assert answer_needs_description(prompt=prompt, label=label), label
    for label in ("A) Sim, aprovar e continuar", "C) Cancelar workflow", "D) Pular este step"):
        assert not answer_needs_description(prompt=prompt, label=label), label


def test_outside_an_approval_gate_a_no_is_just_a_no():
    """Otherwise every yes/no interview question would open a text field."""
    prompt = "2. Quer rodar os testes agora?"
    assert not answer_needs_description(prompt=prompt, label="B) Não")
    assert not answer_needs_description(prompt=prompt, label="A) Sim")


def test_an_english_gate_is_read_like_a_portuguese_one():
    """Playbooks are in English; the agent does not always translate the block.

    Without this, `approve` did not approve: the step fell into `continue`, the
    engine handed the conversation back to the agent and the gate never closed.
    """

    def answers(label: str) -> str:
        return f"1. Approve the Techspec and continue?\n→ {label}"

    assert classify_outcome(answers("A) Yes, approve and continue")) == "approve"
    assert classify_outcome(answers("B) No, I need changes")) == "adjust"
    assert classify_outcome(answers("C) Cancel workflow")) == "cancel"
    assert classify_outcome(answers("D) Skip this step")) == "skip"


def test_english_approval_block_does_not_get_an_other_option():
    """ "Outro" in a gate becomes free text where the engine expects one of three choices."""
    assert not should_add_other_option(
        prompt="1. Approve the Techspec and continue?",
        option_labels=["Yes, approve and continue", "No, I need changes", "Cancel workflow"],
    )


def test_a_choice_with_text_reaches_the_agent_as_adjust_with_the_reason(monkeypatch):
    """End to end: what the engine reads afterwards has the outcome and the guidance."""
    from pulse.replies.text_questionnaire import parse_text_questionnaire

    block = (
        "```text\n"
        "Preciso de algumas informações antes de continuar.\n"
        "1. Aprovar Techspec e avançar?\n"
        "A) Sim, aprovar e continuar\n"
        "B) Não, preciso de ajustes\n"
        "C) Cancelar workflow\n"
        "```"
    )
    questionnaire = parse_text_questionnaire(block)

    class _Bridge:
        def __init__(self) -> None:
            self.asked_text = False

        def select(self, prompt, choices, *, title=""):
            return "B"

        def text(self, prompt, *, title="", default=""):
            self.asked_text = True
            return "trocar a seção de cache"

    bridge = _Bridge()
    answers = TextualPromptHandler(bridge).run_parsed_questionnaire(questionnaire)

    assert bridge.asked_text, "the field must open even without `(descreva)` in the label"
    assert "trocar a seção de cache" in answers
    assert classify_outcome(answers) == "adjust"


def test_the_text_request_reaches_the_dock_queue_as_its_own_prompt():
    """The field is a second request in the queue; that is how the dock draws it.

    Uses the real `PromptBridge`: the jump from `select` to `text` is what the
    user was not seeing happen.
    """
    import threading

    from pulse.replies.text_questionnaire import parse_text_questionnaire
    from pulse.tui.adapters.prompt_bridge import PromptKind

    questionnaire = parse_text_questionnaire(
        "```text\n"
        "Preciso de algumas informações antes de continuar.\n"
        "1. Aprovar Techspec e avançar?\n"
        "A) Sim, aprovar e continuar\n"
        "B) Não, preciso de ajustes\n"
        "C) Cancelar workflow\n"
        "```"
    )
    bridge = PromptBridge()
    answers: list[str | None] = []

    worker = threading.Thread(
        target=lambda: answers.append(
            TextualPromptHandler(bridge).run_parsed_questionnaire(questionnaire)
        )
    )
    worker.start()

    kinds: list[PromptKind] = []
    replies = ["B", "trocar a seção de cache"]
    while len(kinds) < 2:
        request = bridge.poll(timeout=5)
        assert request is not None, f"no question after {kinds}"
        kinds.append(request.kind)
        request.future.set_result(replies[len(kinds) - 1])

    worker.join(timeout=5)

    assert kinds == [PromptKind.SELECT, PromptKind.TEXT], "picking B opens the field"
    assert "trocar a seção de cache" in (answers[0] or "")


@pytest.mark.parametrize(
    "answers",
    [
        "→ Outro — renomeie o campo cancel_reason para motivo",
        "→ Outro — não pular a validação, detalhe mais",
        "→ B) Ajustar (descreva) — pode pular a seção de métricas",
    ],
)
def test_typed_text_never_cancels_or_skips_the_step(answers: str) -> None:
    from pulse.replies.approval import CANCEL, SKIP, classify_outcome

    assert classify_outcome(answers) not in {CANCEL, SKIP}


def test_picked_skip_option_still_skips() -> None:
    from pulse.replies.approval import SKIP, classify_outcome

    assert classify_outcome("→ C) Pular esta fase") == SKIP
