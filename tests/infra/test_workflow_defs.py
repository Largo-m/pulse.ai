"""The definitions Pulse can run; none of them come from files."""

from __future__ import annotations

import re
from pathlib import Path

from pulse.domain.workflow import AgentDef, StepDef, WorkflowDef
from pulse.store.workflow_defs import (
    delete_workflow,
    get_agent,
    get_workflow,
    list_workflows,
    save_agent,
    save_workflow,
)


def test_a_fresh_database_already_has_the_factory_loops():
    """Factory config seeds the database; it is not a catalog in code."""
    workflows = {item.id: item for item in list_workflows()}

    assert set(workflows) >= {
        "default",
        "new-issue",
        "quick-fix",
        "review",
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
        "review",
        "review-fix",
    ]
    assert [step.requires_approval for step in workflows["new-issue"].steps] == [
        True,
        True,
        True,
        False,
        True,
        False,
    ]
    assert get_agent("prd") is not None


def test_the_review_loop_runs_outside_the_spec_pipeline():
    """Same agents as the spec pipeline, different phase: no PRD or tasks here."""
    review = get_workflow("review")

    assert review is not None
    assert review.default_prompt, "reviews the current branch; there is nothing to ask"
    assert [step.agent_id for step in review.steps] == ["review", "review-fix"]
    assert [step.requires_approval for step in review.steps] == [True, False]
    fix = review.steps[1]
    assert (fix.repeat_from, fix.repeat_max) == ("review", 3)
    for step in review.steps:
        assert ".pulse/reviews/" in step.prompt_template
        assert "<slug>/reviews/" not in step.prompt_template


def test_every_factory_step_renders_with_what_the_engine_offers():
    """A placeholder without a value is a `TemplateError` at run time, caught here first."""
    from pulse.orchestrator.render import render

    context = dict.fromkeys(
        (
            "user_prompt",
            "workspace",
            "workflow_id",
            "run_id",
            "step_id",
            "step_label",
            "previous_summary",
            "previous_status",
            "artifacts",
        ),
        "x",
    )
    first_step = dict(context, previous_summary="", previous_status="", artifacts="")

    for workflow in list_workflows():
        for step in workflow.steps:
            render(step.prompt_template, context)
            render(step.prompt_template, first_step)


def test_factory_agents_carry_their_playbook_and_defer_on_runtime():
    prd = get_agent("prd")

    assert prd is not None
    assert "Ambiguity Ledger" in prd.instructions
    assert prd.permission_policy == "deny_writes"
    assert (prd.runtime, prd.model) == ("", "")


def test_the_default_agent_defers_to_the_machine():
    """Empty field means "use the default"; a fixed runtime would freeze `pulse init`."""
    agent = get_agent("default")

    assert agent is not None
    assert agent.runtime == ""
    assert agent.model == ""


def test_domain_markdown_lives_only_in_the_factory_seed():
    """Domain `.md` files are seed data: only `store/factory` loads them.

    The engine must not know phases by name. A `.md` read once into the database
    is fine; one read at run time would reintroduce that coupling.
    """
    package = Path(__file__).resolve().parents[2] / "pulse"
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
        if seed_dir not in path.parents
        and re.search(
            r"pulse\.store\.factory|from pulse\.store import factory",
            path.read_text(encoding="utf-8"),
        )
    ]

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


def test_repo_inspecting_loops_ship_with_a_default_task():
    """Loops that do not depend on a user request are seeded with `default_prompt`."""
    workflows = {item.id: item for item in list_workflows()}

    assert workflows["analyze-codebase"].default_prompt == "Mapear codebase existente"
    assert workflows["setup-project"].default_prompt == "Novo projeto"
    assert workflows["new-issue"].default_prompt == ""
    assert workflows["quick-fix"].default_prompt == ""
    assert workflows["default"].default_prompt == ""


def test_db_seeded_before_the_column_gets_the_task_on_migration(tmp_path: Path):
    """Existing users must not keep seeing the text field.

    `ALTER` gives `''` to existing rows and seeding does not rerun on a seeded
    database, so the backfill closes that gap.
    """
    import sqlite3

    from pulse.store.db import connect

    db_path = tmp_path / "antigo.db"
    connect(db_path).close()

    raw = sqlite3.connect(str(db_path))
    raw.execute("ALTER TABLE workflow_defs DROP COLUMN default_prompt")
    raw.commit()
    raw.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    assert workflows["analyze-codebase"].default_prompt == "Mapear codebase existente"
    assert workflows["setup-project"].default_prompt == "Novo projeto"


def test_backfill_does_not_undo_user_edits(tmp_path: Path):
    from pulse.store import factory
    from pulse.store.db import connect

    db_path = tmp_path / "editado.db"
    connection = connect(db_path)
    connection.execute(
        "UPDATE workflow_defs SET default_prompt = ? WHERE id = ?",
        ("Do meu jeito", "analyze-codebase"),
    )
    factory.backfill_default_prompts(connection)
    connection.commit()
    connection.close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    assert workflows["analyze-codebase"].default_prompt == "Do meu jeito"


def test_unattended_loops_do_not_ask_for_approval():
    """Codebase analysis and project setup run from start to finish.

    They do not depend on a user request and none of their steps require approval.
    """
    workflows = {item.id: item for item in list_workflows()}

    for workflow_id in ("analyze-codebase", "setup-project"):
        approving = [
            step.step_id for step in workflows[workflow_id].steps if step.requires_approval
        ]
        assert approving == [], f"{workflow_id} still stops for approval at {approving}"

    for workflow_id, step_id in (
        ("analyze-codebase", "codebase-explore"),
        ("setup-project", "setup-interview"),
    ):
        step = next(s for s in workflows[workflow_id].steps if s.step_id == step_id)
        assert "Aprovar {{step_label}}" not in step.prompt_template

    assert [step.requires_approval for step in workflows["new-issue"].steps] == [
        True,
        True,
        True,
        False,
        True,
        False,
    ]


def test_old_db_drops_the_approval_request_on_open(tmp_path: Path):
    """Existing users keep the old row in the database, and `seed` does not rewrite it."""
    from pulse.store import factory
    from pulse.store.db import connect

    db_path = tmp_path / "antigo.db"
    connection = connect(db_path)
    connection.executemany(
        """
        UPDATE workflow_steps
           SET requires_approval = 1, prompt_template = prompt_template || ?
         WHERE workflow_id = ? AND step_id = ?
        """,
        [
            (f"\n\n1. {factory.APPROVAL_MARK}\n", workflow_id, step_id)
            for workflow_id, step_id in factory.UNATTENDED_STEPS
        ],
    )
    connection.commit()
    connection.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    for workflow_id, step_id in factory.UNATTENDED_STEPS:
        step = next(s for s in workflows[workflow_id].steps if s.step_id == step_id)
        assert step.requires_approval is False
        assert factory.APPROVAL_MARK not in step.prompt_template


def test_user_rewritten_template_is_not_touched(tmp_path: Path):
    """Without the factory block the row belongs to the user; the migration leaves it alone."""
    from pulse.store import factory
    from pulse.store.db import connect

    db_path = tmp_path / "editado.db"
    connection = connect(db_path)
    connection.execute(
        """
        UPDATE workflow_steps SET prompt_template = ?
         WHERE workflow_id = 'analyze-codebase' AND step_id = 'codebase-explore'
        """,
        ("Explore do meu jeito.",),
    )
    connection.commit()
    connection.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    step = next(s for s in workflows["analyze-codebase"].steps if s.step_id == "codebase-explore")
    assert step.prompt_template == "Explore do meu jeito."
    assert factory.APPROVAL_MARK


def test_seeded_db_gains_the_merge_phase_on_open(tmp_path: Path):
    """The merge layer must reach users who already have a database.

    `seed` is `INSERT OR IGNORE` and does not run on a seeded database; `is_seeded`
    counts factory ids and fails when the factory gains rows. Without it, new
    factory agents would only reach fresh installs.
    """
    from pulse.store.db import connect

    db_path = tmp_path / "antigo.db"
    connection = connect(db_path)
    connection.execute("DELETE FROM workflow_steps WHERE step_id IN ('review', 'review-fix')")
    connection.execute("DELETE FROM agent_defs WHERE id IN ('review', 'review-fix')")
    connection.execute(
        """
        UPDATE workflow_steps SET prompt_template = ?
         WHERE workflow_id = 'new-issue' AND step_id = 'prd'
        """,
        ("PRD do meu jeito.",),
    )
    connection.commit()
    connection.close()

    connect(db_path).close()

    workflows = {item.id: item for item in list_workflows(db_path=db_path)}
    steps = {step.step_id: step for step in workflows["new-issue"].steps}
    assert (steps["review"].position, steps["review-fix"].position) == (5, 6)
    assert steps["review"].requires_approval is True
    assert steps["review-fix"].requires_approval is False
    assert get_agent("review", db_path=db_path) is not None
    assert get_agent("review-fix", db_path=db_path) is not None
    assert steps["prd"].prompt_template == "PRD do meu jeito."


def test_artifact_writers_do_not_run_with_deny_writes():
    """`deny_writes` rejects `write`/`edit` regardless of the path.

    The review phase exists to produce `reviews/round-NNN.md`; under the spec
    phases' policy the file would never reach disk or the artifacts pane. As
    [pulse.replies.permission] states, a step that writes is `ask` or `auto_approve`.
    """
    from pulse.replies.permission import decide_permission

    params = {
        "toolCall": {"kind": "write"},
        "options": [
            {"optionId": "allow-once", "kind": "allow_once"},
            {"optionId": "reject-once", "kind": "reject_once"},
        ],
    }

    for agent_id in ("review", "review-fix"):
        agent = get_agent(agent_id)
        assert agent is not None
        assert decide_permission(params, policy=agent.permission_policy) != {
            "outcome": {"outcome": "selected", "optionId": "reject-once"}
        }, f"{agent_id} cannot write what its phase exists to produce"


def test_only_review_offers_skip():
    """Skipping a spec is out of scope: PRD/Techspec/Tasks keep three options.

    Label and engine must agree: `classify_outcome` maps the choice to `skipped`
    by substring, so a label without "Pular" would promise what the engine won't do.
    """
    from pulse.replies.approval import SKIP, classify_outcome

    workflows = {item.id: item for item in list_workflows()}
    offering = [
        step.step_id
        for workflow in workflows.values()
        for step in workflow.steps
        if step.requires_approval and "Pular" in step.prompt_template
    ]

    assert offering == ["review", "review"]

    step = next(s for s in workflows["new-issue"].steps if s.step_id == "review")
    option = next(
        line.strip() for line in step.prompt_template.splitlines() if line.strip().startswith("C)")
    )
    assert classify_outcome(f"→ {option}") == SKIP


def test_merge_layer_is_a_capped_loop():
    """Review, fix, review again until nothing else is requested.

    The cap matches the playbook's convergence contract (round 3 closes, round 4
    does not exist); otherwise the engine would stop where the text promises to go on.
    """
    steps = {step.step_id: step for step in get_workflow("new-issue").steps}

    assert steps["review-fix"].repeat_from == "review"
    assert steps["review-fix"].repeat_max == 3
    assert steps["review"].position < steps["review-fix"].position
    repeating = [
        step.step_id for workflow in list_workflows() for step in workflow.steps if step.repeat_from
    ]
    assert repeating == ["review-fix", "review-fix"]

    for workflow_id in ("new-issue", "review"):
        steps = {step.step_id: step for step in get_workflow(workflow_id).steps}
        assert steps["review-fix"].repeat_max == 3
        assert "repeats" in steps["review"].prompt_template.lower()
        assert "next: repeat" in steps["review-fix"].prompt_template
        assert "next: close" in steps["review"].prompt_template
        assert "next: close" not in steps["review-fix"].prompt_template
