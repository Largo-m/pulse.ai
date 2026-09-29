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


def test_a_fresh_database_already_has_the_factory_loops():
    """A config de fábrica é semente do banco, não catálogo em código."""
    workflows = {item.id: item for item in list_workflows()}

    assert set(workflows) >= {
        "default",
        "new-issue",
        "quick-fix",
        "setup-project",
        "analyze-codebase",
    }
    assert workflows["default"].is_default is True
    assert workflows["default"].steps[0].prompt_template == "{{user_prompt}}"
    assert [step.step_id for step in workflows["new-issue"].steps] == [
        "prd",
        "techspec",
        "tasks",
        "implement",
    ]
    # O último step de um pipeline executa: não há o que aprovar depois dele.
    assert [step.requires_approval for step in workflows["new-issue"].steps] == [
        True,
        True,
        True,
        False,
    ]
    assert get_agent("prd") is not None


def test_every_factory_step_renders_with_what_the_engine_offers():
    """Placeholder sem valor é `TemplateError` em run — e não em produção."""
    from pulse.prompts.render import render

    context = dict.fromkeys(
        (
            "user_prompt",
            "workspace",
            "workflow_id",
            "run_id",
            "step_id",
            "step_label",
            "previous_summary",
            "artifacts",
        ),
        "x",
    )
    # Primeiro step de uma run: não há resumo anterior nem artefato ainda.
    first_step = dict(context, previous_summary="", artifacts="")

    for workflow in list_workflows():
        for step in workflow.steps:
            render(step.prompt_template, context)
            render(step.prompt_template, first_step)


def test_factory_agents_carry_their_playbook_and_defer_on_runtime():
    prd = get_agent("prd")

    assert prd is not None
    assert "Ambiguity Ledger" in prd.instructions
    assert prd.permission_policy == "deny_writes"
    # Runtime/model de fábrica congelariam a escolha feita no `pulse init`.
    assert (prd.runtime, prd.model) == ("", "")


def test_the_default_agent_defers_to_the_machine():
    """Campo vazio = "use o padrão"; um runtime fixo congelaria o `pulse init`."""
    agent = get_agent("default")

    assert agent is not None
    assert agent.runtime == ""
    assert agent.model == ""


def test_domain_markdown_lives_only_in_the_factory_seed():
    """O `.md` de domínio é semente, não catálogo: só `store/factory` o carrega.

    O que o refactor proíbe é o motor conhecer fase por nome. Um `.md` que vira
    linha do banco uma vez e nunca mais é lido não reintroduz isso — mas um
    `.md` lido em run reintroduziria, então a fronteira é testada.
    """
    package = Path(__file__).resolve().parent.parent / "pulse"
    seed_dir = package / "store" / "factory"
    leftovers = [
        path.relative_to(package)
        for path in package.rglob("*")
        if path.is_file()
        and path.suffix != ".py"
        and "__pycache__" not in path.parts
        and seed_dir not in path.parents
    ]

    assert leftovers == []

    readers = [
        path.relative_to(package)
        for path in package.rglob("*.py")
        if seed_dir not in path.parents and "store.factory" in path.read_text(encoding="utf-8")
    ]

    # Só quem abre o banco semeia. Ninguém mais importa a fábrica.
    assert readers == [Path("store/db.py")]


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
    assert "demo" not in {item.id for item in list_workflows()}


def test_unknown_ids_are_none_not_an_invented_default():
    assert get_workflow("nao-existe") is None
    assert get_agent("nao-existe") is None
