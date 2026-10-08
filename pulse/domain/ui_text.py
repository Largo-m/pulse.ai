"""Portuguese copy that Pulse composes outside the TUI for an interactive screen.

The product speaks Portuguese to its user while code, errors and logs are in
English. Most screen text lives with the TUI, but the engine, the reply
builders, the run log and the client also compose text a person reads on
screen: run notices, the blocked-step menu, dialog labels, status words. That
copy lives here, in one place, so wording is reviewed together and never
drifts between the live screen and the recorded history.

It sits in `domain/` because it is the one package every layer (engine,
replies, history, acp, client) may import without depending on the TUI.
"""

from __future__ import annotations

import re

# Run notices narrated by the engine.
RUN_STOPPED_BY_USER = "Run parada pelo usuário"
AGENT_SESSION_RESTARTED = "Sessão do agente reiniciada"
LOOP_START = "o início do laço"


def run_stopped_at(label: str) -> str:
    return f"Run parada em {label}"


def loop_closed(label: str) -> str:
    return f"{label}: nada a corrigir — laço encerrado"


def step_skipped_by_user(label: str) -> str:
    return f"{label} pulado pelo usuário"


def run_blocked_at(label: str, reason: str) -> str:
    return f"Run bloqueada em {label}: {reason}"


def retrying_step(label: str) -> str:
    return f"Refazendo {label}"


def retrying_step_with_guidance(label: str) -> str:
    return f"Refazendo {label} com orientação do usuário"


def agent_session_restart_failed(error: str) -> str:
    return f"Não consegui reiniciar a sessão do agente: {error}"


def loop_ceiling_reached(label: str, max_rounds: int) -> str:
    return f"{label}: teto de {max_rounds} rodadas atingido — o que sobrou vai no relatório"


def loop_round_requested(label: str, number: int) -> str:
    return f"{label} pediu a {number}ª rodada"


def loop_last_round_requested(label: str, number: int, who: str) -> str:
    return f"{label} pediu a {number}ª rodada — a última: só {who} roda"


# The menu offered when a step fails or is blocked.
RETRY = "Refazer"
RETRY_RESOLVED = "Refazer — já resolvi"
GIVE_GUIDANCE = "Outro — dizer o que fazer"
STOP = "Parar"
SKIP_STEP = "Pular este step"
STOP_RUN = "Parar a run"
STEP_NOT_COMPLETED = "O step não foi concluído."
GUIDANCE_QUESTION = "O que o agente deve fazer nesta nova tentativa?"


def step_blocked_title(label: str) -> str:
    return f"{label} está bloqueado"


def step_failed_title(label: str) -> str:
    return f"Step {label} falhou"


# Why a step did not settle, shown under the menu title.
STEP_CANCELLED = "step cancelado"
STEP_NOT_APPROVED = "step não aprovado"
NO_APPROVAL_NOR_OUTCOME = "o agente encerrou sem o bloco de aprovação nem um desfecho válido"
AGENT_DID_NOT_COMPLETE = "o agente não concluiu o step"
OUTCOME_NOT_DECLARED = (
    "o agente encerrou sem declarar o desfecho do step — "
    "não dá para afirmar que ele entregou o que o step pede"
)
BLOCKED_WITHOUT_REASON = "o agente declarou bloqueio sem dizer o motivo"


def agent_stopped_responding(detail: str) -> str:
    return f"o agente parou de responder — {detail}"


def agent_session_dropped(detail: str) -> str:
    return f"a sessão do agente caiu — {detail}"


def step_crashed(detail: str) -> str:
    return f"o step quebrou — {detail}"


# Phase markers and notices from the agent session.
def continuation_label(phase_label: str, turn: int) -> str:
    """`turn` counts from 1, the first turn being the phase itself."""
    return f"{phase_label} — continuação ({turn})"


def model_notice(model: str) -> str:
    return f"Modelo: {model}"


# The screens read these two markers back; parsing them here keeps the producer
# and its readers on the same wording.
_CONTINUATION_SUFFIX = re.compile(r"\s+—\s+continuação \(\d+\)$", re.IGNORECASE)
_MODEL_NOTICE = re.compile(r"^Modelo:\s*(.+)$", re.IGNORECASE)


def phase_label_of(title: str) -> str:
    """The phase label a `continuation_label` title was built from."""
    return _CONTINUATION_SUFFIX.sub("", title).strip()


def model_of_notice(title: str) -> str | None:
    """The model a `model_notice` names; `None` for any other title."""
    match = _MODEL_NOTICE.match(title)
    return match.group(1).strip() if match else None


# Dialog bubbles and the answers recorded for them.
QUESTION_TITLE = "Pergunta"
ANSWER_TITLE = "Você"
ANSWER_CANCELLED = "Cancelado"
ANSWER_YES = "Sim"
ANSWER_NO = "Não"

# Questions, permissions and plans offered to the user.
DEFAULT_QUESTIONNAIRE_TITLE = "Preciso de algumas informações antes de continuar."
QUESTIONNAIRE_NOTICE = "Questionário interativo"
OTHER_DESCRIBE_OPTION = "Outro (descreva)"
FREE_TEXT_ANSWER_PREFIX = "Outro — "
MULTI_SELECT_HINT = "(escolha uma ou mais)"
PLAN_APPROVAL_TITLE = "Aprovar plano?"
PLAN_FALLBACK_NAME = "Plano"
OPTION_FALLBACK = "Opção"
ALLOW_ONCE = "Permitir esta vez"
REJECT_ONCE = "Recusar"
PERMISSION_KIND_LABELS = {
    "allow_once": ALLOW_ONCE,
    "allow_always": "Sempre permitir",
    "reject_once": REJECT_ONCE,
    "reject_always": "Sempre recusar",
}
PERMISSION_PROMPT_FALLBACK = "O agente pede permissão para continuar."

# Status words, keyed by the raw status value.
AWAITING_YOU = "precisa de você"
RUNNING = "executando"
STATUS_LABELS = {
    "pending": "pendente",
    "in_progress": RUNNING,
    "running": RUNNING,
    "awaiting_input": AWAITING_YOU,
    "awaiting_approval": AWAITING_YOU,
    "approved": "aprovado",
    "blocked": "bloqueado",
    "stopped": "parado",
    "done": "concluído",
    "skipped": "pulado",
    "failed": "falhou",
}


def waiting_since(held: str) -> str:
    """`há 3min`: how long a run has been waiting for its user."""
    return f"há {held}"


# Error entries the client adds to the run's screen, titled like the TUI's own.
ERROR_TITLE = "Erro"
WORKFLOW_FAILED_TITLE = "Workflow falhou"
