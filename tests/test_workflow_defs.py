"""As definições que o Pulse sabe rodar — nenhuma delas vem de arquivo."""

from __future__ import annotations

from pathlib import Path

from pulse.store.workflow_defs import (
    AgentDef,
    StepDef,
    WorkflowDef,
    delete_workflow,
    get_agent,
    get_workflow,
    list_workflows,
    save_agent,
    save_workflow,
)


def test_a_fresh_database_already_has_the_default_workflow():
    """A config de fábrica é semente do banco: o pacote não traz `.md` nenhum."""
    workflows = list_workflows()

    assert [item.id for item in workflows] == ["default"]
    default = workflows[0]
    assert default.is_default is True
    assert [step.step_id for step in default.steps] == ["run"]
    assert default.steps[0].prompt_template == "{{user_prompt}}"
    assert default.steps[0].requires_approval is True
    assert get_agent("default") is not None


def test_the_default_agent_defers_to_the_machine():
    """Campo vazio = "use o padrão"; um runtime fixo congelaria o `pulse init`."""
    agent = get_agent("default")

    assert agent is not None
    assert agent.runtime == ""
    assert agent.model == ""


def test_the_package_ships_no_domain_files():
    """O pacote é só Python: nenhum `AGENT.md`, `PHASE.md` ou skill embutida."""
    package = Path(__file__).resolve().parent.parent / "pulse"
    leftovers = [
        path
        for path in package.rglob("*")
        if path.is_file() and path.suffix != ".py" and "__pycache__" not in path.parts
    ]

    assert leftovers == []


def test_saving_a_workflow_replaces_its_steps():
    save_agent(AgentDef(id="tester", label="Tester"))
    first = WorkflowDef(
        id="demo",
        label="Demo",
        steps=(
            StepDef("demo", "a", 1, "A", "tester", "{{user_prompt}}", True),
            StepDef("demo", "b", 2, "B", "tester", "{{previous_summary}}", False),
        ),
    )
    save_workflow(first)

    # Um step removido da definição tem de sumir, não virar órfão.
    save_workflow(
        WorkflowDef(
            id="demo",
            label="Demo v2",
            steps=(StepDef("demo", "a", 1, "A", "tester", "{{user_prompt}}", True),),
        )
    )

    loaded = get_workflow("demo")
    assert loaded is not None
    assert loaded.label == "Demo v2"
    assert [step.step_id for step in loaded.steps] == ["a"]


def test_steps_come_back_in_position_order():
    save_agent(AgentDef(id="tester", label="Tester"))
    save_workflow(
        WorkflowDef(
            id="demo",
            label="Demo",
            steps=(
                StepDef("demo", "third", 0, "3", "tester", "x", False),
                StepDef("demo", "first", 0, "1", "tester", "x", False),
                StepDef("demo", "second", 0, "2", "tester", "x", False),
            ),
        )
    )

    loaded = get_workflow("demo")
    assert loaded is not None
    # `save_workflow` renumera pela ordem em que os steps chegaram.
    assert [step.step_id for step in loaded.steps] == ["third", "first", "second"]


def test_deleting_a_workflow_takes_its_steps_along():
    save_agent(AgentDef(id="tester", label="Tester"))
    save_workflow(
        WorkflowDef(
            id="demo",
            label="Demo",
            steps=(StepDef("demo", "a", 1, "A", "tester", "x", False),),
        )
    )

    delete_workflow("demo")

    assert get_workflow("demo") is None
    assert [item.id for item in list_workflows()] == ["default"]


def test_unknown_ids_are_none_not_an_invented_default():
    assert get_workflow("nao-existe") is None
    assert get_agent("nao-existe") is None
