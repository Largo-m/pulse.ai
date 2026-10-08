"""Item-list protocol read from the agent response (`pulse:items` block).

Lets one step fan out into N isolated sub-steps whose count is only known after
the previous step ran. The engine never reads artifacts: the agent enumerates
the items in a fenced block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from pulse.domain.workflow import StepDef
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord, fan_out_child_id

BLOCK = re.compile(r"```pulse:items[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
ITEM = re.compile(r"^[ \t>*-]*([^\s:—–-][^:—–]*?)[ \t]*[:—–-][ \t]*(\S.*)$")

MAX_ITEMS = 40
POSITION_STRIDE = 1000


@dataclass(frozen=True)
class Item:
    id: str
    label: str


def parse_items(text: str) -> tuple[Item, ...]:
    """Items of the last `pulse:items` block; empty when there is no block.

    The last block wins because the agent may re-present an adjusted list.
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
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        items.append(Item(id=item_id, label=match.group(2).strip()))
        if len(items) >= MAX_ITEMS:
            break
    return tuple(items)


def expand(
    run: run_store.RunRecord, step: StepDef, previous_summary: str
) -> list[tuple[StepDef, Item | None]]:
    """Expand a definition step into the steps the run will actually execute.

    With `fan_out`, one step per item enumerated by the previous step, each with
    its own `step_id`. An empty list runs the step once, as if `fan_out` were unset.
    Only the run in memory changes; the caller persists it with `run_store.save`.
    """
    if not step.fan_out:
        return [(step, None)]

    items = parse_items(previous_summary)
    if not items:
        return [(step, None)]

    base = run.step(step.step_id)
    base_position = base.position if base is not None else step.position * POSITION_STRIDE

    units: list[tuple[StepDef, Item | None]] = []
    children: list[StepRecord] = []
    for index, item in enumerate(items, start=1):
        step_id = fan_out_child_id(step.step_id, item.id)
        label = item.label or item.id
        position = base_position + index
        units.append((step.for_item(step_id=step_id, label=label, position=position), item))
        children.append(
            StepRecord(step_id=step_id, position=position, label=label, agent_id=step.agent_id)
        )
    run.expand_step(step.step_id, children)
    return units
