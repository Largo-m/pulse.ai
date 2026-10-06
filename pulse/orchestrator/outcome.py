"""O terceiro protocolo que o Pulse lê da resposta do agente: o desfecho do step.

Os outros dois são o questionário de aprovação ([pulse.prompts.approval]) e a
lista de itens do fan-out ([pulse.orchestrator.fanout]). Este existe porque, sem
ele, "o step terminou bem" queria dizer apenas "o agente encerrou o turno": um
agente que respondia *"não consigo, falta a credencial"* fechava o turno com
`end_turn` como qualquer outro, o step era gravado `done` e o step seguinte
rodava em cima de uma entrega que não existiu.

O motor continua sem interpretar prosa. Ele não procura "não consegui" no texto
— procura um bloco cercado que ele mesmo especificou, do mesmo jeito que já faz
com `pulse:items`. Quem afirma o desfecho é o agente, e afirmar é um ato
explícito: silêncio não vale como sucesso.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: ```pulse:outcome … ``` — cercado e nomeado, para não colidir com um bloco de
#: código que o agente tenha citado no mesmo texto.
BLOCK = re.compile(r"```pulse:outcome[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
FIELD = re.compile(
    r"^[ \t>*-]*(status|reason|needs|motivo|precisa|next|proximo|próximo)[ \t]*:[ \t]*(.*)$",
    re.IGNORECASE,
)

DONE = "done"
BLOCKED = "blocked"
#: O agente encerrou sem declarar nada. Não é sucesso nem bloqueio ainda — é a
#: ausência do único sinal que o motor tem, e vale uma pergunta antes de valer
#: um veredito. Ver [pulse.orchestrator.engine._attempt_step].
MISSING = "missing"

_DONE_WORDS = frozenset({"done", "ok", "concluido", "concluído", "sucesso", "success", "pronto"})
_BLOCKED_WORDS = frozenset(
    {"blocked", "bloqueado", "bloqueio", "travado", "stuck", "impedido", "failed", "falhou"}
)
#: Palavras com que o agente diz "isto não está ao meu alcance". Não são lidas
#: da prosa: são o valor do campo `needs`, que só existe para esta decisão —
#: gastar um turno mandando o agente resolver sozinho o que ele já declarou
#: depender de outra pessoa é queimar token para chegar no mesmo lugar.
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
#: Palavras com que o agente pede mais uma volta do laço, no campo `next`. Só
#: valem num step que a definição marcou como repetível — ver `repeat_from` em
#: [pulse.store.workflow_defs]. Num step comum, o campo é ignorado: quem decide
#: que um laço existe é o workflow, não o agente.
_REPEAT_WORDS = frozenset({"repeat", "repetir", "again", "denovo", "nova-rodada", "loop"})
#: Palavras com que quem **abre** o laço diz que não sobrou nada a corrigir, no
#: mesmo campo `next`. O laço termina ali, e o resto da faixa não roda.
_CLOSE_WORDS = frozenset({"close", "fechar", "encerrar", "end", "clean", "limpo"})

#: Um motivo de bloqueio vira título de menu e linha de log: sem teto, um agente
#: que cola o stack trace inteiro no `reason` estoura os dois.
REASON_MAX_CHARS = 400


@dataclass(frozen=True)
class Outcome:
    """O que o agente declarou ao fechar o step."""

    status: str
    #: Uma linha explicando o bloqueio, do jeito que o agente escreveu.
    reason: str = ""
    #: Token do campo `needs`. Ver `needs_user`.
    needs: str = ""
    #: Token do campo `next`. Ver `repeats`.
    next: str = ""

    @property
    def delivered(self) -> bool:
        return self.status == DONE

    @property
    def repeats(self) -> bool:
        """O agente pede outra volta do laço.

        Só tem efeito onde a definição declarou um laço, e só quando o step
        entregou: um step bloqueado não pede rodada nova, ele pede gente.
        """
        return self.delivered and self.next in _REPEAT_WORDS

    @property
    def closes(self) -> bool:
        """O agente diz que o laço acabou: nada mais a corrigir.

        Só tem efeito no step que abre um laço — ver
        [pulse.orchestrator.loops.close_loop].
        """
        return self.delivered and self.next in _CLOSE_WORDS

    @property
    def needs_user(self) -> bool:
        """O agente diz que depende de gente, acesso ou permissão.

        Quem responde `True` pula a tentativa de auto-resolução e vai direto
        para a pessoa: o agente não tem como destravar o que ele mesmo disse
        que não está ao alcance dele.
        """
        return self.needs in _NEEDS_USER


def parse_outcome(text: str) -> Outcome:
    """Desfecho do último bloco `pulse:outcome`. Sem bloco, devolve `MISSING`.

    O último, e não o primeiro: um step que passou por uma continuação tem dois
    blocos no texto acumulado, e o que vale é o de baixo — o mesmo critério do
    `pulse:items`.
    """
    matches = BLOCK.findall(text or "")
    if not matches:
        return Outcome(status=MISSING)

    fields: dict[str, str] = {}
    for line in matches[-1].splitlines():
        match = FIELD.match(line.strip())
        if match is None:
            continue
        key = match.group(1).lower()
        # O agente pode responder no idioma do prompt; o motor guarda um nome só.
        key = {
            "motivo": "reason",
            "precisa": "needs",
            "proximo": "next",
            "próximo": "next",
        }.get(key, key)
        fields.setdefault(key, _clean(match.group(2)))

    raw_status = fields.get("status", "").lower()
    reason = fields.get("reason", "")[:REASON_MAX_CHARS]
    needs = fields.get("needs", "").split()[0].lower().strip(".,;") if fields.get("needs") else ""
    nxt = fields.get("next", "").split()[0].lower().strip(".,;") if fields.get("next") else ""

    if raw_status in _DONE_WORDS:
        return Outcome(status=DONE, next=nxt)
    if raw_status in _BLOCKED_WORDS:
        return Outcome(status=BLOCKED, reason=reason, needs=needs)
    if not raw_status:
        return Outcome(status=MISSING)
    # Bloco presente com status que ninguém reconhece. Vale como bloqueio, e não
    # como sucesso: o motor não tem como afirmar que a entrega aconteceu, e o
    # preço de errar para o lado do bloqueio é uma pergunta a mais na tela.
    return Outcome(
        status=BLOCKED,
        reason=reason or f"o agente declarou um desfecho que o Pulse não conhece: `{raw_status}`",
        needs=needs,
    )


def _clean(value: str) -> str:
    """Tira o comentário de fim de linha que o exemplo do protocolo carrega."""
    text = value.strip()
    if "#" in text:
        text = text.split("#", 1)[0]
    return text.strip().strip("`").strip()
