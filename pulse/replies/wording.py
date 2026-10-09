"""How Pulse presents an agent's question to the user: injected options, fallbacks, labels.

The reply builders turn the agent's request into what the user picks from, so
the words of those options live with them; the screens and the run log read
them from here.
"""

from __future__ import annotations

DEFAULT_QUESTIONNAIRE_TITLE = "Preciso de algumas informações antes de continuar."
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
