from pathlib import Path

import pytest

from pulse.store.workflow_defs import AgentDef, StepDef, WorkflowDef, save_agent, save_workflow


@pytest.fixture(autouse=True)
def _isolate_pulse_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PULSE_DB", str(tmp_path / "pulse.db"))


def make_workflow(
    workflow_id: str = "demo",
    *,
    steps: list[tuple[str, str]] | None = None,
    label: str = "Demo",
    requires_approval: bool = True,
    prompt_template: str = "{{user_prompt}}",
    fan_out: tuple[str, ...] | set[str] = (),
    requires_outcome: bool = True,
    repeat: tuple[str, str, int] | None = None,
) -> WorkflowDef:
    """Grava um workflow de teste no banco e devolve a definição.

    Os testes precisam de um workflow com forma conhecida; como o Pulse não
    traz nenhum além do `default` de um step, cada teste semeia o seu.

    `repeat=(step_id, volta_para, teto)` marca um laço: aquele step pode mandar
    a run voltar e repetir o trecho.
    """
    entries = steps or [("one", "Um"), ("two", "Dois")]
    save_agent(AgentDef(id="tester", label="Tester"))
    definition = WorkflowDef(
        id=workflow_id,
        label=label,
        steps=tuple(
            StepDef(
                workflow_id=workflow_id,
                step_id=step_id,
                position=index,
                label=step_label,
                agent_id="tester",
                prompt_template=prompt_template,
                requires_approval=requires_approval,
                fan_out=step_id in fan_out,
                requires_outcome=requires_outcome,
                repeat_from=repeat[1] if repeat and repeat[0] == step_id else "",
                repeat_max=repeat[2] if repeat and repeat[0] == step_id else 0,
            )
            for index, (step_id, step_label) in enumerate(entries, start=1)
        ),
    )
    save_workflow(definition)
    return definition


@pytest.fixture
def demo_workflow() -> WorkflowDef:
    return make_workflow()
