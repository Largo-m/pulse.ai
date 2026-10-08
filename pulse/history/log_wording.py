"""The words of the run log: dialog bubbles, recorded answers and phase markers.

The session log writes them into `run_events` and the cockpit draws the same
ones live, so a past run reopens exactly as it was shown.
"""

from __future__ import annotations

QUESTION_TITLE = "Pergunta"
ANSWER_TITLE = "Você"
ANSWER_CANCELLED = "Cancelado"
ANSWER_YES = "Sim"
ANSWER_NO = "Não"
QUESTIONNAIRE_NOTICE = "Questionário interativo"


def continuation_label(phase_label: str, turn: int) -> str:
    """The marker of a phase's later turn; `turn` counts from 1, the phase itself."""
    return f"{phase_label} — continuação ({turn})"
