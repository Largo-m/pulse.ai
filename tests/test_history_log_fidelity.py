"""O histórico tem que mostrar o mesmo que a sessão viva mostrou.

O log gravado passa pelos mesmos rótulos do cockpit
([pulse.history.tool_detail.build_tool_labels]), e a releitura devolve cada linha ao
tipo dela. Enquanto o banco guardava `kind="Tool"` com o `title` cru do ACP, uma
run reaberta virava uma fileira de "v Tool" sem dizer o que o agente leu,
rodou ou escreveu.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_workflow

from pulse.acp.session_runner import AcpSessionRunner
from pulse.history.events import LogKind
from pulse.history.models import HistoryItem, HistoryStatus, HistoryStep
from pulse.store import runs as run_store
from pulse.store.runs import StepRecord
from pulse.tui.hydrate import hydrate_history_item


def _runner(workspace: Path, run_id: str = "run-1", step_id: str = "plan") -> AcpSessionRunner:
    runner = AcpSessionRunner(["agent", "acp"], cwd=str(workspace), enable_mcp_ask=False)
    runner.bind_run(run_id)
    runner._phase_id = step_id
    return runner


def _run(workspace: Path, run_id: str = "run-1") -> str:
    make_workflow("demo", steps=[("plan", "Planejar")])
    record = run_store.create_run(
        run_id=run_id,
        workflow_id="demo",
        workspace=workspace,
        user_prompt="fazer algo",
        steps=[StepRecord(step_id="plan", position=1, label="Planejar")],
    )
    return record.id


def _update(**fields) -> dict:
    return {"update": {"sessionUpdate": "tool_call", "toolCallId": "t-1", **fields}}


def _hydrated(workspace: Path, run_id: str = "run-1"):
    item = HistoryItem(
        run_id=run_id,
        workflow_id="demo",
        workflow_label="Demo",
        title="demo",
        prompt="fazer algo",
        status=HistoryStatus.DONE,
        updated_at="2026-09-30T10:00:00+00:00",
        steps=[HistoryStep(id="plan", label="Planejar", status="done")],
    )
    return hydrate_history_item(item, workspace)


def test_cada_tool_guarda_o_tipo_que_a_tela_mostrou(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._record_run_event(
        _update(title="Read File", kind="read", rawInput={"path": str(tmp_path / "a.py")})
    )
    runner._record_run_event(
        {
            "update": {
                "sessionUpdate": "tool_call",
                "toolCallId": "t-2",
                "title": "Shell",
                "kind": "execute",
                "rawInput": {"command": "pytest -q"},
            }
        }
    )

    events = run_store.list_events(run_id)
    assert [(event["kind"], event["title"]) for event in events] == [
        ("Read", "a.py"),
        ("Shell", "pytest -q"),
    ]


def test_o_historico_reabre_com_os_tipos_em_vez_de_tool_generico(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    runner._record_run_event(
        _update(title="Read File", kind="read", rawInput={"path": str(tmp_path / "a.py")})
    )

    state = _hydrated(tmp_path, run_id)

    assert [(entry.kind, entry.title) for entry in state.entries] == [
        (LogKind.READ, "a.py")
    ]


def test_a_fala_do_agente_volta_inteira_no_balao(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    fala = "linha um. " * 400  # bem além do antigo teto de 2000 caracteres

    runner._text_buffer.append(fala)
    runner._flush_text()

    state = _hydrated(tmp_path, run_id)
    entry = state.entries[0]
    assert entry.kind == LogKind.ASSISTANT
    assert entry.body == fala.strip()


def test_o_cabecalho_do_passo_fica_no_log(tmp_path: Path):
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._begin_phase("Planejar")

    state = _hydrated(tmp_path, run_id)
    assert [(entry.kind, entry.title) for entry in state.entries] == [
        (LogKind.INFO, "Planejar")
    ]


def test_um_update_tardio_nao_apaga_o_rotulo_do_tool(tmp_path: Path):
    """O `rawOutput` chega noutro evento; a linha já tinha o arquivo."""
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)

    runner._record_run_event(
        _update(title="Write File", kind="write", rawInput={"path": str(tmp_path / "PRD.md")})
    )
    runner._record_run_event(
        {
            "update": {
                "sessionUpdate": "tool_call_update",
                "toolCallId": "t-1",
                "status": "completed",
            }
        }
    )

    events = run_store.list_events(run_id)
    assert [(event["kind"], event["title"]) for event in events] == [("Write", "PRD.md")]


def test_artefato_sai_do_tool_mesmo_sem_kind_do_acp(tmp_path: Path):
    """Runtime que só manda o nome do tool também rende artefato.

    A aba de artefatos do histórico vinha vazia porque o registro dependia do
    campo `kind` do ACP, que nem todo runtime preenche.
    """
    run_id = _run(tmp_path)
    runner = _runner(tmp_path, run_id)
    (tmp_path / "PRD.md").write_text("# PRD\n", encoding="utf-8")

    runner._record_run_event(
        _update(title="Write", toolName="write_file", rawInput={"path": str(tmp_path / "PRD.md")})
    )

    assert [item["path"] for item in run_store.list_artifacts(run_id)] == ["PRD.md"]

    state = _hydrated(tmp_path, run_id)
    assert [(item.path, item.has_content) for item in state.artifacts] == [("PRD.md", True)]
    assert state.phase_has_artifacts(), "a aba precisa abrir para o artefato da run"
