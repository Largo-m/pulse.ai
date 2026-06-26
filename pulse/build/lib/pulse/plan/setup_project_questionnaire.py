from __future__ import annotations

from pathlib import Path

from pulse.presentation.prompt.text_questionnaire import TextQuestion, TextQuestionnaire

DEFAULT_SETUP_QUESTIONNAIRE = TextQuestionnaire(
    title="Preciso de algumas informações antes de continuar.",
    questions=(
        TextQuestion(
            id="q1",
            prompt="1. O que você está construindo?",
            options=(
                ("A", "Plataforma de simulação / paper trading"),
                ("B", "Sistema de gestão de portfólio ou finanças pessoais"),
                ("C", "Projeto full-stack de estudo ou portfólio"),
                ("D", "Plataforma completa pronta para produção"),
                ("E", "Outro (descreva)"),
            ),
        ),
        TextQuestion(
            id="q2",
            prompt="2. Quem é o público-alvo e qual problema resolve?",
            options=(
                ("A", "Usuários iniciantes aprendendo a usar o produto"),
                ("B", "Desenvolvedores estudando arquitetura"),
                ("C", "Uso pessoal"),
                ("D", "Público geral"),
                ("E", "Outro (descreva)"),
            ),
        ),
        TextQuestion(
            id="q3",
            prompt="3. Qual é o foco da v1 neste momento?",
            options=(
                ("A", "Consolidar o que existe — gaps, testes, estabilidade"),
                ("B", "Completar features pendentes"),
                ("C", "Preparar para deploy"),
                ("D", "Adicionar novas features (descreva)"),
                ("E", "Outro (descreva escopo e exclusões)"),
            ),
        ),
        TextQuestion(
            id="q4",
            prompt="4. Há restrições críticas?",
            options=(
                ("A", "Sem prazo — evolução contínua local"),
                ("B", "Prazo curto (descreva)"),
                ("C", "Apenas ambiente local"),
                ("D", "Preparar para produção em breve"),
                ("E", "Outro (descreva)"),
            ),
        ),
    ),
)


def project_specs_complete(workspace: Path) -> bool:
    project_md = workspace / ".specs" / "project" / "PROJECT.md"
    if not project_md.is_file():
        return False
    content = project_md.read_text(encoding="utf-8").lower()
    markers = ("**vision:**", "**for:**", "**solves:**", "## goals", "## scope")
    return sum(marker in content for marker in markers) >= 4


def should_run_pulse_questionnaire(
    *,
    workspace: Path,
    ask_question_count: int,
    agent_already_asked: bool,
) -> bool:
    if ask_question_count > 0 or agent_already_asked:
        return False
    if project_specs_complete(workspace):
        return False
    return True
