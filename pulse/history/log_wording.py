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


def phase_title(phase_label: str, turn: int = 1) -> str:
    """The phase's log title; `turn` counts from 1, the phase itself, and later turns say so."""
    return f"{phase_label} — continuação ({turn})" if turn > 1 else phase_label
