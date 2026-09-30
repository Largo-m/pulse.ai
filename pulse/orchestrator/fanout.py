"""O segundo protocolo que o Pulse lê da resposta do agente: a lista de itens.

O primeiro é o questionário de aprovação ([pulse.prompts.approval]). Este existe
porque um step às vezes não é *um* trabalho: "implementar as tasks" são N
trabalhos, e cada um merece sessão isolada e linha própria no painel — mas
quantos são só se sabe depois que o step anterior rodou.

O motor continua sem ler artefato. Ele não abre `tasks.md`, não conhece `### T1`
nem nome de arquivo nenhum: quem enumera é o agente, num bloco cercado que o
Pulse sabe achar. Trocar `tasks.md` por outra coisa não muda uma linha daqui.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: ```pulse:items … ``` — cercado e nomeado para não colidir com um bloco de
#: código que o agente tenha citado no mesmo texto.
BLOCK = re.compile(r"```pulse:items[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
#: `T1 — Criar o endpoint` / `T1 - Criar o endpoint` / `T1: Criar o endpoint`.
#: O id é o que o prompt do item vai citar; o título é o que aparece no painel.
ITEM = re.compile(r"^[ \t>*-]*([^\s:—–-][^:—–]*?)[ \t]*[:—–-][ \t]*(\S.*)$")

#: Teto de segurança. Um agente que devolve 200 itens errou a conta, e abrir 200
#: sessões ACP sairia caro antes de alguém perceber.
MAX_ITEMS = 40


@dataclass(frozen=True)
class Item:
    id: str
    label: str


def parse_items(text: str) -> tuple[Item, ...]:
    """Itens do último bloco `pulse:items`. Texto sem bloco devolve vazio.

    O último, e não o primeiro: quando o agente reapresenta a lista depois de um
    ajuste, a versão que vale é a de baixo.
    """
    matches = BLOCK.findall(text or "")
    if not matches:
        return ()
    items: list[Item] = []
    seen: set[str] = set()
    for line in matches[-1].splitlines():
        match = ITEM.match(line.strip())
        if match is None:
            continue
        item_id = match.group(1).strip()
        # Id repetido viraria `step_id` duplicado, e `run_steps` tem chave
        # (run_id, step_id): o segundo sobrescreveria o primeiro em silêncio.
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        items.append(Item(id=item_id, label=match.group(2).strip()))
        if len(items) >= MAX_ITEMS:
            break
    return tuple(items)
