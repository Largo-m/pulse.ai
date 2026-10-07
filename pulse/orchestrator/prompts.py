"""Prompt text written by Pulse itself (orchestrator protocol, not task content).

Everything else in the prompt comes from the user (`workflow_steps.prompt_template`).
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


_OUTCOME_PROTOCOL = """\

---

## Como encerrar este step

Se faltar uma informação que só o usuário tem, **pergunte a ele** — há um canal
de pergunta nesta sessão e perguntar não encerra o step. Bloqueio é o último
recurso, não o jeito de pedir um dado.

Termine sempre com este bloco, e nada depois dele:

```pulse:outcome
status: done
```

`status: done` afirma que o que este step pede foi entregue. Não declare `done`
com ressalva no texto: se ficou algo por fazer, o desfecho é outro.

Se não conseguiu entregar, declare o bloqueio:

```pulse:outcome
status: blocked
reason: o que impediu, em uma linha
needs: user
```

`needs: user` só quando depender de outra pessoa, de um acesso, de uma
credencial ou de uma permissão que você não tem. Deixe o campo de fora quando
for algo que você ainda pode tentar resolver.
"""

_UNBLOCK = """\
## Bloqueio declarado no step `{step_id}`

Você declarou que não conseguiu concluir:

{reason}

Se isso está ao seu alcance — criar o que falta, instalar a dependência, ler o
que ainda não leu, tentar outro caminho — resolva agora e conclua o step.

Se depende mesmo de outra pessoa, de um acesso ou de uma permissão que você não
tem, declare o bloqueio de novo dizendo exatamente **o que precisa e de quem**,
com `needs: user`.

Encerre com o bloco ```pulse:outcome, como antes.
"""

_OUTCOME_REMINDER = """\
## Desfecho do step `{step_id}`

Você encerrou sem declarar o desfecho, e sem ele o Pulse não sabe se o step
entregou o que pedia.

Se está tudo entregue, responda apenas com o bloco de desfecho. Se ficou algo
por fazer e você consegue terminar agora, termine e depois declare. Se não
consegue, declare o bloqueio com o motivo.

```pulse:outcome
status: done
```
"""


def outcome_protocol() -> str:
    """Closing instructions appended to the prompt of a step without approval.

    Engine protocol rather than step content, so `prompt_template` authors need
    not know about it.
    """
    return _OUTCOME_PROTOCOL


def build_unblock_prompt(*, step_id: str, reason: str) -> str:
    """Give the agent a chance to unblock itself before involving the user."""
    return _UNBLOCK.format(step_id=step_id, reason=reason.strip() or "(sem motivo declarado)")


def build_outcome_reminder_prompt(*, step_id: str) -> str:
    """A forgotten outcome block is not a block: ask for it before concluding."""
    return _OUTCOME_REMINDER.format(step_id=step_id)


def guidance_block(guidance: str) -> str:
    """Guidance the user wrote when asking to retry a step."""
    text = guidance.strip()
    if not text:
        return ""
    return (
        "\n\n## Orientação do usuário para esta tentativa\n\n"
        "A tentativa anterior falhou. Siga a orientação abaixo — ela tem\n"
        "precedência sobre a instrução original deste step:\n\n"
        f"{text}\n"
    )
