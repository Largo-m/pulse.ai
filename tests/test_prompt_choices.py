import time

from pulse.prompts.approval import (
    answer_needs_description,
    classify_outcome,
    picked_answers,
)
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


def test_o_campo_abre_para_qualquer_jeito_de_pedir_texto():
    """O agente parafraseia e traduz: reconhecer `(descreva)` literal não bastava."""
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


def test_o_campo_nao_abre_em_rotulo_que_so_menciona_o_verbo():
    """Pedido ao usuário vem em parênteses, colchete ou cauda — não solto no meio."""
    for label in (
        "A) Sim, aprovar e continuar",
        "C) Cancelar workflow",
        "B) A documentação que descreve o fluxo está correta",
        "B) Quick fix: reutilizar TokenResponseAdapter",
    ):
        assert not option_requires_description(label), label


def test_num_portao_de_aprovacao_todo_nao_abre_o_campo():
    """A garantia que não depende da redação do agente.

    Aprovar, pular e cancelar dizem sozinhos o que fazer. Todo o resto volta ao
    agente como "o usuário quer mudanças" — sem texto, ele refaz o step no escuro.
    """
    prompt = "1. Aprovar Techspec e avançar?"
    for label in ("B) Não, preciso de ajustes", "B) Não", "B) No, I need changes"):
        assert answer_needs_description(prompt=prompt, label=label), label
    for label in ("A) Sim, aprovar e continuar", "C) Cancelar workflow", "D) Pular este step"):
        assert not answer_needs_description(prompt=prompt, label=label), label


def test_fora_do_portao_de_aprovacao_um_nao_continua_sendo_so_um_nao():
    """Senão toda pergunta de sim/não da entrevista abriria um campo de texto."""
    prompt = "2. Quer rodar os testes agora?"
    assert not answer_needs_description(prompt=prompt, label="B) Não")
    assert not answer_needs_description(prompt=prompt, label="A) Sim")


def test_o_portao_em_ingles_e_lido_como_o_em_portugues():
    """Os playbooks são em inglês; o agente nem sempre traduz o bloco.

    Sem isto `approve` não aprovava: o step caía em `continue`, o motor devolvia a
    conversa ao agente e o portão nunca fechava.
    """
    def answers(label: str) -> str:
        return f"1. Approve the Techspec and continue?\n→ {label}"

    assert classify_outcome(answers("A) Yes, approve and continue")) == "approve"
    assert classify_outcome(answers("B) No, I need changes")) == "adjust"
    assert classify_outcome(answers("C) Cancel workflow")) == "cancel"
    assert classify_outcome(answers("D) Skip this step")) == "skip"


def test_bloco_de_aprovacao_em_ingles_nao_ganha_um_outro():
    """"Outro" num portão vira texto livre onde o motor espera uma das três."""
    assert not should_add_other_option(
        prompt="1. Approve the Techspec and continue?",
        option_labels=["Yes, approve and continue", "No, I need changes", "Cancel workflow"],
    )


def test_a_escolha_com_texto_chega_ao_agente_como_ajuste_e_com_o_motivo(monkeypatch):
    """Ponta a ponta: o que o motor lê depois tem o desfecho e a orientação."""
    from pulse.prompts.text_questionnaire import parse_text_questionnaire

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

    assert bridge.asked_text, "o campo tem de abrir mesmo sem `(descreva)` no rótulo"
    assert "trocar a seção de cache" in answers
    assert classify_outcome(answers) == "adjust"


def test_o_pedido_de_texto_chega_a_fila_do_dock_como_um_prompt_proprio():
    """O campo é um segundo pedido na fila — é assim que o dock o desenha.

    Testa com o `PromptBridge` de verdade: é o pulo do `select` para o `text` que
    o usuário não estava vendo acontecer.
    """
    import threading

    from pulse.prompts.text_questionnaire import parse_text_questionnaire
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
    deadline = time.monotonic() + 5
    while len(kinds) < 2 and time.monotonic() < deadline:
        request = bridge.poll()
        if request is None:
            time.sleep(0.01)
            continue
        kinds.append(request.kind)
        request.future.set_result(replies[len(kinds) - 1])

    worker.join(timeout=5)

    assert kinds == [PromptKind.SELECT, PromptKind.TEXT], "escolher B abre o campo"
    assert "trocar a seção de cache" in (answers[0] or "")
