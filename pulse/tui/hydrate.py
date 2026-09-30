"""Reconstrói o cockpit a partir de uma run já gravada.

Tudo que a tela precisa está no banco: `run_steps` dá a sidebar, `run_events` dá
o stream e `run_artifacts` dá o painel. Não há leitura do store do runtime nem
varredura de pasta — uma run feita em qualquer agente reabre igual.

Duas portas, o mesmo material: [hydrate_history_item] monta a tela parada do
histórico, e [restore_run] devolve o passado a um cockpit que vai continuar
rodando. Retomar sem isto abria a run mostrando só "concluído" nos steps
anteriores — sem log, sem tool, sem duração.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pulse.history.events import ArtifactItem, LogEntry, LogKind, PhaseItem, PhaseStatus
from pulse.history.models import HistoryItem
from pulse.store import runs as run_store
from pulse.tui.artifacts import artifact_has_content, artifact_key
from pulse.tui.state import CockpitState

_NO_LOGS = "Nenhum log persistido para esta run."
_STEP_TO_PHASE = {
    "pending": PhaseStatus.PENDING,
    "running": PhaseStatus.RUNNING,
    "done": PhaseStatus.DONE,
    "skipped": PhaseStatus.SKIPPED,
    "failed": PhaseStatus.FAILED,
    "blocked": PhaseStatus.BLOCKED,
}


def hydrate_history_item(item: HistoryItem, workspace: Path) -> CockpitState:
    state = CockpitState()
    state.workflow_id = item.workflow_id
    state.workflow_label = item.workflow_label.upper()
    state.phases = [
        PhaseItem(id=step.id, label=step.label, status=_STEP_TO_PHASE.get(step.status, PhaseStatus.PENDING))
        for step in item.steps
    ]
    state.surface_title = item.title.upper()
    state.running = False
    state.acp_sessions = [
        {"phase_id": step.id, "label": step.label, "acp_session_id": step.acp_session_id}
        for step in item.steps
        if step.acp_session_id
    ]
    if state.acp_sessions:
        state.acp_session_id = state.acp_sessions[-1]["acp_session_id"]

    _stamp_elapsed(state, item.run_id)
    state.entries = _load_entries(item.run_id, state.phases)
    state.artifacts = _load_artifacts(item.run_id, workspace)
    displayable = [artifact for artifact in state.artifacts if artifact.has_content]
    if displayable:
        state.selected_artifact_path = displayable[-1].path

    logged = {entry.phase_id for entry in state.entries if entry.phase_id}
    selected = 0
    for index, phase in enumerate(state.phases):
        if phase.id in logged or phase.status == PhaseStatus.RUNNING:
            selected = index
            break
    state.selected_phase_index = selected
    state.selected_nav_kind = "phase"
    state._follow_live = False
    state._next_entry_id = max((entry.entry_id for entry in state.entries), default=0) + 1
    return state


def restore_run(state: CockpitState, run_id: str, workspace: Path) -> None:
    """Põe no cockpit o que a run já tinha, antes de ela voltar a rodar.

    Retomar continua a **mesma** run: o `run_id` é o mesmo, e `run_events` guarda
    tudo que já aconteceu nela. Começar a tela zerada jogava isso fora — os steps
    que já tinham fechado reapareciam como "concluído" e nada mais.

    `sync_phases` preserva fase por id, então o que é posto aqui sobrevive ao
    `phases.sync` que o motor manda em seguida.
    """
    record = run_store.load_run(run_id)
    if record is None:
        return

    state.sync_phases([{"id": step.step_id, "label": step.label} for step in record.steps])
    status = {step.step_id: step.status for step in record.steps}
    for phase in state.phases:
        phase.status = _STEP_TO_PHASE.get(status.get(phase.id, ""), PhaseStatus.PENDING)
        if phase.status == PhaseStatus.RUNNING:
            # Nada está rodando numa run que acabou de reabrir. Gravado como
            # `running` é step que a queda pegou no meio — ele vai ser refeito, e
            # deixá-lo assim daria ao `begin_phase` seguinte uma fase "em curso"
            # para fechar, com duração do tamanho do mundo.
            phase.status = PhaseStatus.PENDING
    _stamp_elapsed(state, run_id)

    state.entries = _load_entries(run_id, state.phases, placeholder=False)
    state.artifacts = _load_artifacts(run_id, workspace)
    # Os ids continuam de onde pararam: entrada nova com id repetido faria o
    # stream reescrever uma linha antiga em vez de acrescentar a dela.
    state._next_entry_id = max((entry.entry_id for entry in state.entries), default=0) + 1
    state.notify()


def _stamp_elapsed(state: CockpitState, run_id: str) -> None:
    """Duração de cada step, do que ficou gravado em `run_steps`.

    A tela conta tempo em `time.monotonic()`, que não existe mais depois do
    processo terminar. Para uma run relida, o par (0, duração) é o que mostra a
    duração correta sem o relógio voltar a andar.
    """
    record = run_store.load_run(run_id)
    if record is None:
        return
    durations = {
        step.step_id: _seconds(step.started_at, step.ended_at) for step in record.steps
    }
    for phase in state.phases:
        seconds = durations.get(phase.id)
        if seconds is not None:
            phase.started_at = 0.0
            phase.ended_at = seconds


def _seconds(started_at: str, ended_at: str) -> float | None:
    start = _parse_stamp(started_at)
    end = _parse_stamp(ended_at)
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds()
    return delta if delta >= 0 else None


def _parse_stamp(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _load_entries(
    run_id: str, phases: list[PhaseItem], *, placeholder: bool = True
) -> list[LogEntry]:
    entries: list[LogEntry] = []
    for row in run_store.list_events(run_id):
        title = row.get("title", "").strip()
        detail = row.get("detail", "").strip()
        if not title and not detail:
            continue
        is_tool = row.get("kind") == "Tool"
        entries.append(
            LogEntry(
                kind=LogKind.TOOL if is_tool else LogKind.ASSISTANT,
                title=title[:160] or detail[:160],
                detail=detail,
                # O stream desenha a fala do agente a partir de `body`; a de tool,
                # de `detail`. Sem isso o balão do assistente reabre vazio.
                body="" if is_tool else detail,
                entry_id=len(entries) + 1,
                tool_id=row.get("tool_id", ""),
                phase_id=row.get("step_id", ""),
            )
        )
    if entries or not placeholder:
        return entries
    return [
        LogEntry(
            kind=LogKind.INFO,
            title=_NO_LOGS,
            detail=_NO_LOGS,
            entry_id=index + 1,
            phase_id=phase.id,
        )
        for index, phase in enumerate(phases)
    ]


def _load_artifacts(run_id: str, workspace: Path) -> list[ArtifactItem]:
    by_step = {
        entry["path"]: entry["step_id"] for entry in run_store.list_artifacts(run_id)
    }
    artifacts: list[ArtifactItem] = []
    for path, step_id in by_step.items():
        key = artifact_key(path)
        artifacts.append(
            ArtifactItem(
                path=key,
                phase_id=step_id,
                ready=True,
                has_content=artifact_has_content(key, str(workspace)),
            )
        )
    return artifacts
