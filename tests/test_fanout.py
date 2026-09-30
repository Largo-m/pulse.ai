"""Fan-out: um step da definição que vira N na run, um por item enumerado."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import make_workflow
from tests.test_engine_steps import (  # noqa: F401
    _approved,
    _blocked,
    _delivered,
    _install,
    _Runner,
    wired,
)

from pulse.orchestrator import engine
from pulse.orchestrator.fanout import MAX_ITEMS, parse_items
from pulse.orchestrator.engine import run_workflow
from pulse.store import runs as run_store


def _block(*lines: str) -> str:
    body = "\n".join(lines)
    return f"Resumo da fase.\n\n```pulse:items\n{body}\n```\n"


# --------------------------------------------------------------- o parser


def test_reads_the_items_from_the_fenced_block():
    items = parse_items(_block("T1 — Criar o endpoint", "T2 - Montar o CSV", "T3: Testar"))

    assert [(item.id, item.label) for item in items] == [
        ("T1", "Criar o endpoint"),
        ("T2", "Montar o CSV"),
        ("T3", "Testar"),
    ]


def test_text_without_a_block_has_no_items():
    """Sem bloco não há fan-out — e não há erro: o step roda uma vez."""
    assert parse_items("Escrevi tasks.md com 3 tarefas.") == ()
    assert parse_items("") == ()


def test_the_last_block_wins():
    """Ajuste reapresentado: a lista que vale é a de baixo."""
    text = _block("T1 — Antigo") + _block("T1 — Novo", "T2 — Extra")

    assert [item.label for item in parse_items(text)] == ["Novo", "Extra"]


def test_a_repeated_id_is_dropped():
    """Id repetido viraria `step_id` duplicado e sobrescreveria o primeiro."""
    items = parse_items(_block("T1 — Primeiro", "T1 — Repetido", "T2 — Segundo"))

    assert [item.id for item in items] == ["T1", "T2"]


def test_the_item_count_is_capped():
    items = parse_items(_block(*(f"T{index} — Task" for index in range(1, MAX_ITEMS + 10))))

    assert len(items) == MAX_ITEMS


# --------------------------------------------------------------- o motor


def test_each_item_becomes_its_own_step_and_its_own_session(wired, monkeypatch, tmp_path: Path):
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
        prompt_template="{{user_prompt}}{{#if item_id}} | {{item_id}} {{item_index}}/{{item_total}}{{/if}}",
    )
    runner = _Runner(
        [
            _approved(_block("T1 — Criar o endpoint", "T2 — Montar o CSV")),
            _approved(),
            _approved(),
        ]
    )
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="exportar csv",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    # O step `run` sumiu: no lugar dele, um por item.
    assert [(step.step_id, step.label, step.status) for step in record.steps] == [
        ("plan", "Planejar", "done"),
        ("run:T1", "Criar o endpoint", "done"),
        ("run:T2", "Montar o CSV", "done"),
    ]
    # Uma sessão por item, cada uma sabendo só do seu.
    assert runner.prompts[1].endswith("| T1 1/2")
    assert runner.prompts[2].endswith("| T2 2/2")


def test_the_panel_receives_the_expanded_step_list(wired, monkeypatch, tmp_path: Path):
    """O painel montou as fases pela definição; o fan-out muda isso no meio."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    runner = _Runner([_approved(_block("T1 — Um", "T2 — Dois")), _approved(), _approved()])
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    last = runner._stream.statuses[-1]
    assert [step["id"] for step in last["steps"]] == ["plan", "run:T1", "run:T2"]
    assert [step["label"] for step in last["steps"]] == ["Planejar", "Um", "Dois"]


def test_a_step_that_declares_nothing_still_runs_once(wired, monkeypatch, tmp_path: Path):
    """Protocolo que o agente não seguiu não é motivo para a run parar."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    runner = _Runner([_approved("Escrevi o plano, sem bloco."), _approved()])
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 0
    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["plan", "run"]


def test_resuming_does_not_redo_an_item_that_already_passed(wired, monkeypatch, tmp_path: Path):
    """Retomar refaz o item que ficou, não a lista inteira."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    summary = _block("T1 — Um", "T2 — Dois")
    # T2 falha: a run para com T1 fechado.
    failing = _Runner([_approved(summary), _approved(), {"approved": False, "outcome": "approve"}])
    _install(monkeypatch, failing)
    assert (
        run_workflow(
            workflow_id="demo",
            user_prompt="x",
            stream=failing._stream,
            prompt_handler=failing._prompt_handler,
            render_header=False,
        )
        != 0
    )
    run_id = run_store.list_runs(tmp_path)[0].id

    resumed = _Runner([_approved()])
    _install(monkeypatch, resumed)
    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=resumed._stream,
        prompt_handler=resumed._prompt_handler,
        render_header=False,
        resume_run_id=run_id,
    )

    assert code == 0
    # Só T2 rodou de novo — `plan` e `run:T1` já estavam fechados.
    assert len(resumed.prompts) == 1
    record = run_store.load_run(run_id)
    assert record is not None
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("plan", "done"),
        ("run:T1", "done"),
        ("run:T2", "done"),
    ]


def test_items_keep_their_order_beyond_nine(wired, monkeypatch, tmp_path: Path):
    """`run_steps` ordena por posição: T10 não pode cair entre T1 e T2."""
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    ids = [f"T{index}" for index in range(1, 12)]
    runner = _Runner(
        [_approved(_block(*(f"{item} — Task {item}" for item in ids)))]
        + [_approved() for _ in ids]
    )
    _install(monkeypatch, runner)

    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["plan"] + [f"run:{item}" for item in ids]


def test_every_item_is_recorded_before_the_first_one_runs(
    wired, monkeypatch, tmp_path: Path
):
    """Os N filhos vão para o banco na expansão, não quando cada um começa.

    Filho que só existia na memória sumia se a run caísse no meio do fan-out:
    o histórico reabria com as tasks que já tinham rodado e mais nenhuma.
    """
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    ids = [f"T{index}" for index in range(1, 11)]
    # O bloco enumera dez; a segunda task derruba a sessão e o usuário para.
    runner = _Runner(
        [
            _approved(_block(*(f"{item} — Task {item}" for item in ids))),
            _approved(),
            RuntimeError("o processo do agente encerrou"),
        ]
    )
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == 1
    record = run_store.list_runs(tmp_path)[0]
    assert [step.step_id for step in record.steps] == ["plan"] + [f"run:{item}" for item in ids]
    assert [step.status for step in record.steps[:3]] == ["done", "done", "failed"]
    assert {step.status for step in record.steps[3:]} == {"pending"}


def test_resuming_keeps_the_fan_out_instead_of_redoing_the_parent_step(
    wired, monkeypatch, tmp_path: Path
):
    """O pai não volta: ao retomar, o bloco de itens ainda é o do step anterior.

    A busca pelo resumo anterior parava no step pai — que o fan-out apagou. Sem
    ele, a varredura ia até o fim e pegava o resumo da última task, que não tem
    bloco `pulse:items`: o fan-out desmontava e `run` rodava como step único.
    """
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
    )
    first = _Runner(
        [
            _approved(_block("T1 — Um", "T2 — Dois")),
            _approved("terminei a T1, sem bloco de itens"),
            RuntimeError("o processo do agente encerrou"),
        ]
    )
    first._prompt_handler.choice = "stop"
    _install(monkeypatch, first)
    run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=first._stream,
        prompt_handler=first._prompt_handler,
        render_header=False,
    )
    run_id = run_store.list_runs(tmp_path)[0].id

    resumed = _Runner([_approved()])
    _install(monkeypatch, resumed)
    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=resumed._stream,
        prompt_handler=resumed._prompt_handler,
        render_header=False,
        resume_run_id=run_id,
    )

    assert code == 0
    record = run_store.load_run(run_id)
    assert record is not None
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("plan", "done"),
        ("run:T1", "done"),
        ("run:T2", "done"),
    ]


def test_a_blocked_task_does_not_drag_the_next_ones_along(wired, monkeypatch, tmp_path: Path):
    """O caso que deu origem a tudo: T2 travou e T3 rodou assim mesmo.

    Cada task tem sessão isolada, então a de T3 nem saberia que T2 não
    entregou. Quem tem de saber é o motor — e ele para na task bloqueada.
    """
    make_workflow(
        "demo",
        steps=[("plan", "Planejar"), ("run", "Implementar")],
        fan_out=("run",),
        requires_approval=False,
    )
    runner = _Runner(
        [
            _delivered(_block("T1 — Um", "T2 — Dois", "T3 — Três")),
            _delivered(),
            _blocked("a migration depende de uma decisão de schema", needs="user"),
        ]
    )
    runner._prompt_handler.choice = "stop"
    _install(monkeypatch, runner)

    code = run_workflow(
        workflow_id="demo",
        user_prompt="x",
        stream=runner._stream,
        prompt_handler=runner._prompt_handler,
        render_header=False,
    )

    assert code == engine.RUN_BLOCKED
    record = run_store.list_runs(tmp_path)[0]
    assert [(step.step_id, step.status) for step in record.steps] == [
        ("plan", "done"),
        ("run:T1", "done"),
        ("run:T2", "blocked"),
        ("run:T3", "pending"),
    ]
    assert len(runner.prompts) == 3, "T3 nem chegou a abrir sessão"
    # O painel mostra a task travada como bloqueada, não como falha.
    assert runner._stream.statuses[-1]["blocked_ids"] == ["run:T2"]
