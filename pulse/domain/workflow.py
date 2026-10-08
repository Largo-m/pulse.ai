"""Workflow, step and agent definitions: values the engine reads, never code.

They have no identity beyond their ids and no I/O; persistence lives in
[pulse.store.workflow_defs].
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentDef:
    id: str
    label: str
    runtime: str = ""
    model: str = ""
    permission_policy: str = ""
    instructions: str = ""


@dataclass(frozen=True)
class StepDef:
    workflow_id: str
    step_id: str
    position: int
    label: str
    agent_id: str
    prompt_template: str
    requires_approval: bool
    fan_out: bool = False
    requires_outcome: bool = True
    repeat_from: str = ""
    repeat_max: int = 0


@dataclass(frozen=True)
class WorkflowDef:
    id: str
    label: str
    description: str = ""
    is_default: bool = False
    default_prompt: str = ""
    steps: tuple[StepDef, ...] = ()
