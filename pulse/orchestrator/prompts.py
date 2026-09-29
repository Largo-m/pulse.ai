"""Os dois textos que o próprio Pulse escreve.

Todo o resto do prompt é dado do usuário (`workflow_steps.prompt_template`).
O que sobra aqui não descreve tarefa nenhuma — é só o protocolo do
orquestrador: retomar um step depois do questionário e repassar uma orientação
de nova tentativa. Por isso são constantes, não template configurável.
"""

from __future__ import annotations

from pulse.prompts.approval import ADJUST, format_summary

_CONTINUATION = """\
## Continuação do step `{step_id}`

Resumo do que você produziu até agora:

{summary}

Respostas do usuário ao questionário:

{answers}

{instruction}

Ao terminar, volte a apresentar o bloco ```text de aprovação.
"""

_ADJUST_INSTRUCTION = (
    "Aplique os ajustes pedidos acima. Não recomece do zero: parta do que já "
    "existe e mude só o que foi apontado."
)
_CONTINUE_INSTRUCTION = (
    "Siga a partir do ponto em que parou, incorporando as respostas acima."
)


def build_continuation_prompt(
    *,
    step_id: str,
    summary: str,
    answers: str,
    outcome: str,
) -> str:
    return _CONTINUATION.format(
        step_id=step_id,
        summary=format_summary(summary) or "(Sem resumo anterior.)",
        answers=answers.strip() or "(Sem respostas.)",
        instruction=_ADJUST_INSTRUCTION if outcome == ADJUST else _CONTINUE_INSTRUCTION,
    )


def guidance_block(guidance: str) -> str:
    """Instrução que o usuário escreveu ao mandar refazer um step."""
    text = guidance.strip()
    if not text:
        return ""
    return (
        "\n\n## Orientação do usuário para esta tentativa\n\n"
        "A tentativa anterior falhou. Siga a orientação abaixo — ela tem\n"
        "precedência sobre a instrução original deste step:\n\n"
        f"{text}\n"
    )
