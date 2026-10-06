"""Histórico: as runs deste workspace, lidas do banco.

Antes o histórico era montado varrendo `.pulse/specs/` atrás de `PRD.md` e
`TASK.md` — o que só funcionava para um pipeline específico. Agora a lista é
`runs` + `run_steps`, então qualquer workflow aparece sem o Pulse saber o que
ele faz.
"""

from __future__ import annotations

from pathlib import Path

from pulse import vcs
from pulse.history.models import LIVE_STATUSES, HistoryItem, HistoryStatus, HistoryStep
from pulse.store import runs as run_store
from pulse.store.workflow_defs import get_workflow

_RUN_TO_HISTORY = {
    "pending": HistoryStatus.PENDING,
    "running": HistoryStatus.IN_PROGRESS,
    "awaiting_input": HistoryStatus.AWAITING_INPUT,
    "completed": HistoryStatus.DONE,
    "failed": HistoryStatus.FAILED,
    "stopped": HistoryStatus.STOPPED,
    "blocked": HistoryStatus.BLOCKED,
}


class HistoryCatalog:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace

    def list_items(self) -> list[HistoryItem]:
        """As runs deste workspace: o que está executando primeiro.

        Dentro de cada grupo a ordem continua sendo a mais recente no topo, que
        é como `run_store.list_runs` entrega. O que muda é a prioridade: uma run
        viva é a única da lista em que ainda dá para entrar e participar —
        procurá-la no meio do passado era o caminho errado para o único item
        que não é passado. Run esperando resposta conta como viva, e é a que
        mais precisa estar à mão.
        """
        items = [_item(record) for record in run_store.list_runs(self.workspace)]
        return sorted(items, key=lambda item: item.status not in LIVE_STATUSES)

    def search(self, query: str = "") -> list[HistoryItem]:
        items = self.list_items()
        needle = query.strip().lower()
        if not needle:
            return items
        return [item for item in items if _matches(item, needle)]

    def get(self, item_id: str) -> HistoryItem | None:
        record = run_store.load_run(item_id)
        if record is None or record.workspace_root != str(self.workspace.resolve()):
            return None
        return _item(record)

    def delete(self, item_id: str) -> bool:
        """Remove a run do histórico. `False` = não é deste workspace.

        A checagem de workspace é a mesma do `get`: o histórico só mostra as
        runs daqui, então só essas ele pode apagar.

        O worktree da run vai junto — ele só existia por causa dela. Mas só se
        estiver limpo: trabalho não commitado lá dentro não é nosso para jogar
        fora, e quem apaga uma linha do histórico não está pedindo isso. Sujo,
        o diretório fica (`remove_worktree` recusa sem `--force`), e a run sai
        da lista do mesmo jeito.
        """
        item = self.get(item_id)
        if item is None:
            return False
        self.remove_worktree(item)
        return run_store.delete_run(item_id)

    def remove_worktree(self, item: HistoryItem, *, force: bool = False) -> bool:
        """Desfaz o worktree da run. `False` = não havia, ou o git recusou.

        Esquecer o caminho no banco mesmo quando o diretório já sumiu é de
        propósito: o que sobrava ali era uma oferta de remover algo que não
        existe mais.
        """
        path = item.worktree_path
        if not path:
            return False
        repo = vcs.repo_root(self.workspace)
        removed = False
        if repo is not None and Path(path).exists():
            try:
                vcs.remove_worktree(repo, path, force=force)
                removed = True
            except vcs.GitError:
                return False
        run_store.set_workspace_context(item.run_id, worktree_path="", branch=item.branch)
        item.worktree_path = ""
        return removed or not Path(path).exists()


def search_history(workspace: Path, query: str = "") -> list[HistoryItem]:
    return HistoryCatalog(workspace).search(query)


def _item(record: run_store.RunRecord) -> HistoryItem:
    definition = get_workflow(record.workflow_id)
    return HistoryItem(
        run_id=record.id,
        workflow_id=record.workflow_id,
        workflow_label=definition.label if definition else record.workflow_id,
        title=record.user_prompt.strip() or record.workflow_id,
        prompt=record.user_prompt,
        status=_RUN_TO_HISTORY.get(record.status, HistoryStatus.PENDING),
        updated_at=record.updated_at or record.created_at,
        steps=[
            HistoryStep(
                id=step.step_id,
                label=step.label or step.step_id,
                status=step.status,
                acp_session_id=step.acp_session_id,
            )
            for step in record.steps
        ],
        artifacts=[entry["path"] for entry in run_store.list_artifacts(record.id)],
        branch=record.branch,
        worktree_path=record.worktree_path,
    )


def _matches(item: HistoryItem, needle: str) -> bool:
    haystack = " ".join(
        [
            item.title,
            item.prompt,
            item.workflow_id,
            item.workflow_label,
            item.status.value,
            item.status_label,
        ]
    ).lower()
    return needle in haystack
