"""Step outcome protocol read from the agent response (`pulse:outcome` block).

Without it, a step that merely ended its turn (e.g. "I can't, missing
credentials") was recorded as `done`. The engine does not interpret prose; the
agent must explicitly declare the outcome, and silence is not success.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

BLOCK = re.compile(r"```pulse:outcome[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
FIELD = re.compile(
    r"^[ \t>*-]*(status|reason|needs|motivo|precisa|next|proximo|próximo)[ \t]*:[ \t]*(.*)$",
    re.IGNORECASE,
)


class OutcomeStatus(StrEnum):
    DONE = "done"
    BLOCKED = "blocked"
    MISSING = "missing"


class LoopSignal(StrEnum):
    """What the agent asks of the loop around its step (the `next` field)."""

    REPEAT = "repeat"
    CLOSE = "close"


_DONE_WORDS = frozenset({"done", "ok", "concluido", "concluído", "sucesso", "success", "pronto"})
_BLOCKED_WORDS = frozenset(
    {"blocked", "bloqueado", "bloqueio", "travado", "stuck", "impedido", "failed", "falhou"}
)
_NEEDS_USER = frozenset(
    {
        "user",
        "usuario",
        "usuário",
        "pessoa",
        "human",
        "humano",
        "permission",
        "permissao",
        "permissão",
        "acesso",
        "access",
        "credencial",
        "credential",
        "segredo",
        "secret",
        "decisao",
        "decisão",
    }
)
_REPEAT_WORDS = frozenset({"repeat", "repetir", "again", "denovo", "nova-rodada", "loop"})
_CLOSE_WORDS = frozenset({"close", "fechar", "encerrar", "end", "clean", "limpo"})

REASON_MAX_CHARS = 400


@dataclass(frozen=True)
class Outcome:
    """What the agent declared when closing the step."""

    status: OutcomeStatus
    reason: str = ""
    needs: str = ""
    next: LoopSignal | None = None

    @property
    def delivered(self) -> bool:
        return self.status == OutcomeStatus.DONE

    @property
    def repeats(self) -> bool:
        """The agent requests another loop round (only when the step delivered)."""
        return self.delivered and self.next == LoopSignal.REPEAT

    @property
    def closes(self) -> bool:
        """The agent says the loop is over; see [pulse.orchestrator.loops.close_loop]."""
        return self.delivered and self.next == LoopSignal.CLOSE

    @property
    def needs_user(self) -> bool:
        """The agent depends on a person, access or permission.

        When `True`, the self-unblock attempt is skipped and the user is asked directly.
        """
        return self.needs in _NEEDS_USER


def parse_outcome(text: str) -> Outcome:
    """Outcome of the last `pulse:outcome` block; `MISSING` when there is none.

    The last block wins because a continued step accumulates more than one.
    """
    matches = BLOCK.findall(text or "")
    if not matches:
        return Outcome(status=OutcomeStatus.MISSING)

    fields: dict[str, str] = {}
    for line in matches[-1].splitlines():
        match = FIELD.match(line.strip())
        if match is None:
            continue
        key = match.group(1).lower()
        key = {
            "motivo": "reason",
            "precisa": "needs",
            "proximo": "next",
            "próximo": "next",
        }.get(key, key)
        fields.setdefault(key, _clean(match.group(2)))

    raw_status = _first_word(fields.get("status", ""))
    reason = fields.get("reason", "")[:REASON_MAX_CHARS]
    needs = _first_word(fields.get("needs", ""))
    nxt = _first_word(fields.get("next", ""))

    if raw_status in _DONE_WORDS:
        return Outcome(status=OutcomeStatus.DONE, next=_loop_signal(nxt))
    if raw_status in _BLOCKED_WORDS:
        return Outcome(status=OutcomeStatus.BLOCKED, reason=reason, needs=needs)
    if not raw_status:
        return Outcome(status=OutcomeStatus.MISSING)
    return Outcome(
        status=OutcomeStatus.BLOCKED,
        reason=reason or f"o agente declarou um desfecho que o Pulse não conhece: `{raw_status}`",
        needs=needs,
    )


def _loop_signal(word: str) -> LoopSignal | None:
    if word in _REPEAT_WORDS:
        return LoopSignal.REPEAT
    if word in _CLOSE_WORDS:
        return LoopSignal.CLOSE
    return None


def _clean(value: str) -> str:
    return value.strip().strip("`").strip()


def _first_word(value: str) -> str:
    """`done.`, `**done**` and `done — entreguei` are all the same `done`."""
    words = value.split()
    return words[0].lower().strip(".,;:*_`") if words else ""
