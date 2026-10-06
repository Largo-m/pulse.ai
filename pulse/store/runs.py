"""Estado de execução: runs, steps, log e artefatos.

Tudo que o orquestrador precisa para responder "onde esta run parou" vive aqui.
Nada disso vai para arquivo: o único conteúdo em disco é o que o agente escreve
no workspace, e desse o Pulse guarda só o caminho (`run_artifacts`).

As tabelas são chaveadas por `run_id` e por `workspace_root`, não por
`project_id`: registrar o projeto só para satisfazer uma FK marcaria o workspace
como inicializado e faria o onboarding parar de rodar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pulse.store.db import connect, default_db_path

#: Teto do detalhe gravado. É ele que segura a fala do agente inteira — em
#: 2000 caracteres uma resposta longa reabria cortada no meio, e o histórico
#: mostrava menos do que a sessão viva tinha mostrado.
MAX_DETAIL = 20_000

PENDING = "pending"
RUNNING = "running"
#: A run existe, o agente está vivo, e nada avança porque há uma pergunta aberta
#: na tela de alguém. Status da **run**, não do step: o step continua `running`
#: — ele não terminou, só parou de consumir tempo de agente. Ver
#: [pulse.acp.session_runner._begin_user_wait].
AWAITING_INPUT = "awaiting_input"
DONE = "done"
SKIPPED = "skipped"
FAILED = "failed"
STOPPED = "stopped"
#: O agente rodou e declarou que não tinha como concluir. Diferente de `failed`,
#: que é quebra técnica (sessão caiu, prazo estourou): aqui nada quebrou, a
#: entrega é que não aconteceu. A distinção existe porque o que se faz com cada
#: um é diferente — falha se refaz, bloqueio se destrava.
BLOCKED = "blocked"

#: Um step nesses estados não roda de novo ao retomar. `blocked` fica de fora de
#: propósito: retomar uma run bloqueada tem de refazer o step que travou.
SETTLED = frozenset({DONE, SKIPPED})


@dataclass
class StepRecord:
    step_id: str
    position: int = 0
    label: str = ""
    agent_id: str = ""
    status: str = PENDING
    summary: str = ""
    acp_session_id: str = ""
    started_at: str = ""
    ended_at: str = ""
    #: Tempo que este step passou esperando o usuário, descontado da duração.
    waiting_seconds: float = 0.0
    #: Quantas vezes este step rodou nesta run. Passa de 1 só dentro de um laço.
    rounds: int = 1
    #: Duração líquida das voltas anteriores do laço. Ver `carry_round`.
    carried_seconds: float = 0.0


@dataclass
class RunRecord:
    id: str
    workflow_id: str
    #: Raiz do projeto — a identidade da run, e o que o histórico casa.
    workspace_root: str
    user_prompt: str = ""
    status: str = PENDING
    current_step: str = ""
    created_at: str = ""
    updated_at: str = ""
    #: Worktree desta run, quando ela não rodou na raiz do projeto.
    worktree_path: str = ""
    #: Branch em que a run aconteceu — com ou sem worktree.
    branch: str = ""
    steps: list[StepRecord] = field(default_factory=list)

    @property
    def exec_root(self) -> str:
        """Onde o agente trabalhou: o worktree, ou a raiz quando não houve um."""
        return self.worktree_path or self.workspace_root

    def step(self, step_id: str) -> StepRecord | None:
        for item in self.steps:
            if item.step_id == step_id:
                return item
        return None

    def next_pending(self) -> StepRecord | None:
        for item in self.steps:
            if item.status not in SETTLED:
                return item
        return None

    def is_incomplete(self) -> bool:
        return any(item.status not in SETTLED for item in self.steps)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _root(workspace: str | Path) -> str:
    return str(Path(workspace).resolve())


def _step(row: Any) -> StepRecord:
    return StepRecord(
        step_id=str(row["step_id"]),
        position=int(row["position"] or 0),
        label=str(row["label"] or ""),
        agent_id=str(row["agent_id"] or ""),
        status=str(row["status"] or PENDING),
        summary=str(row["summary"] or ""),
        acp_session_id=str(row["acp_session_id"] or ""),
        started_at=str(row["started_at"] or ""),
        ended_at=str(row["ended_at"] or ""),
        waiting_seconds=float(row["waiting_seconds"] or 0.0),
        rounds=int(row["rounds"] or 1),
        carried_seconds=float(row["carried_seconds"] or 0.0),
    )


def _run(row: Any, steps: list[StepRecord]) -> RunRecord:
    return RunRecord(
        id=str(row["id"]),
        workflow_id=str(row["workflow_id"]),
        workspace_root=str(row["workspace_root"]),
        user_prompt=str(row["user_prompt"] or ""),
        status=str(row["status"] or PENDING),
        current_step=str(row["current_step"] or ""),
        created_at=str(row["created_at"] or ""),
        updated_at=str(row["updated_at"] or ""),
        worktree_path=str(row["worktree_path"] or ""),
        branch=str(row["branch"] or ""),
        steps=steps,
    )


def _steps_for(connection: Any, run_id: str) -> list[StepRecord]:
    rows = connection.execute(
        "SELECT * FROM run_steps WHERE run_id = ? ORDER BY position, step_id",
        (run_id,),
    ).fetchall()
    return [_step(row) for row in rows]


def create_run(
    *,
    run_id: str,
    workflow_id: str,
    workspace: str | Path,
    user_prompt: str,
    steps: list[StepRecord],
    db_path: Path | None = None,
) -> RunRecord:
    now = utc_now()
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO runs
              (id, workflow_id, workspace_root, user_prompt, status, current_step,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                workflow_id,
                _root(workspace),
                user_prompt,
                RUNNING,
                steps[0].step_id if steps else "",
                now,
                now,
            ),
        )
        connection.executemany(
            """
            INSERT INTO run_steps
              (run_id, step_id, position, label, agent_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            # A posição vem do registro, não do índice: o motor espaça os steps
            # (1000, 2000, …) justamente para o fan-out caber entre dois deles.
            # Renumerar aqui punha as tasks do step 2 depois do step 3.
            [
                (run_id, item.step_id, item.position or index, item.label, item.agent_id, PENDING)
                for index, item in enumerate(steps, start=1)
            ],
        )
        connection.commit()
    finally:
        connection.close()
    return RunRecord(
        id=run_id,
        workflow_id=workflow_id,
        workspace_root=_root(workspace),
        user_prompt=user_prompt,
        status=RUNNING,
        current_step=steps[0].step_id if steps else "",
        created_at=now,
        updated_at=now,
        steps=steps,
    )


def load_run(run_id: str, *, db_path: Path | None = None) -> RunRecord | None:
    connection = connect(db_path or default_db_path())
    try:
        row = connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return _run(row, _steps_for(connection, run_id))
    finally:
        connection.close()


def list_runs(
    workspace: str | Path,
    *,
    limit: int = 200,
    db_path: Path | None = None,
) -> list[RunRecord]:
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            "SELECT * FROM runs WHERE workspace_root = ? ORDER BY updated_at DESC LIMIT ?",
            (_root(workspace), limit),
        ).fetchall()
        return [_run(row, _steps_for(connection, str(row["id"]))) for row in rows]
    finally:
        connection.close()


def find_resumable(workspace: str | Path, *, db_path: Path | None = None) -> list[RunRecord]:
    """Runs que pararam no meio — dá para retomar do step onde ficaram.

    Falha entra na lista: é o caso em que mais se quer voltar. Uma run que caiu
    no quinto de dez steps guarda os quatro primeiros em `run_steps`, e retomar
    roda só o que faltou. Só `completed` fica de fora, e ainda assim só quando
    não sobrou step nenhum por fazer.
    """
    return [
        run
        for run in list_runs(workspace, db_path=db_path)
        if run.status != "completed" and run.is_incomplete()
    ]


def update_run(
    run_id: str,
    *,
    status: str | None = None,
    current_step: str | None = None,
    db_path: Path | None = None,
) -> None:
    sets: list[str] = ["updated_at = ?"]
    values: list[Any] = [utc_now()]
    if status is not None:
        sets.append("status = ?")
        values.append(status)
    if current_step is not None:
        sets.append("current_step = ?")
        values.append(current_step)
    values.append(run_id)
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id = ?", values)
        connection.commit()
    finally:
        connection.close()


def set_workspace_context(
    run_id: str,
    *,
    worktree_path: str = "",
    branch: str = "",
    db_path: Path | None = None,
) -> None:
    """Grava onde esta run trabalha e em que branch.

    Separado de `create_run` porque o worktree só existe depois que a run tem
    id: é o id que batiza o diretório. Separado de `update_run` porque não é
    estado de execução — não muda enquanto a run anda, e retomar depende de
    reler exatamente o que ficou aqui.
    """
    if not run_id:
        return
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            "UPDATE runs SET worktree_path = ?, branch = ?, updated_at = ? WHERE id = ?",
            (worktree_path, branch, utc_now(), run_id),
        )
        connection.commit()
    finally:
        connection.close()


def save_step(run_id: str, step: StepRecord, *, db_path: Path | None = None) -> None:
    connection = connect(db_path or default_db_path())
    try:
        # Upsert, e não `UPDATE`: nem todo step existe desde o início da run. O
        # fan-out cria os dele no meio, e um step acrescentado à definição
        # depois também — com `UPDATE` os dois sumiam sem erro nenhum.
        #
        # Em conflito, só o estado é reescrito. `position`, `label` e `agent_id`
        # foram copiados da definição quando a run começou, e editar o workflow
        # depois não pode reescrever o que já aconteceu.
        #
        # `waiting_seconds` fica de fora do `DO UPDATE` de propósito: quem o
        # move é `add_waiting_seconds`, chamado da thread da sessão enquanto o
        # motor segura um `StepRecord` que não sabe da espera. Reescrevê-lo aqui
        # zeraria o tempo de espera recém-somado no primeiro `save_step`.
        # `carried_seconds` também, pelo mesmo motivo: só `carry_round` o move.
        connection.execute(
            """
            INSERT INTO run_steps
              (run_id, step_id, position, label, agent_id,
               status, summary, acp_session_id, started_at, ended_at, waiting_seconds,
               rounds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step_id) DO UPDATE SET
              status = excluded.status,
              summary = excluded.summary,
              acp_session_id = excluded.acp_session_id,
              started_at = excluded.started_at,
              ended_at = excluded.ended_at,
              rounds = excluded.rounds
            """,
            (
                run_id,
                step.step_id,
                step.position,
                step.label,
                step.agent_id,
                step.status,
                step.summary,
                step.acp_session_id,
                step.started_at,
                step.ended_at,
                step.waiting_seconds,
                step.rounds,
            ),
        )
        connection.execute(
            "UPDATE runs SET updated_at = ? WHERE id = ?", (utc_now(), run_id)
        )
        connection.commit()
    finally:
        connection.close()


def add_waiting_seconds(
    run_id: str,
    step_id: str,
    seconds: float,
    *,
    db_path: Path | None = None,
) -> None:
    """Soma tempo de espera do usuário ao step. Soma, e não atribui: um step
    pode parar várias vezes — uma permissão, depois um questionário — e cada
    parada tira o seu pedaço da duração.

    Step que ainda não existe na tabela é ignorado em silêncio: a espera pode
    acontecer antes do primeiro `save_step` (o menu de retomada, por exemplo),
    e perder a contabilidade vale mais do que criar linha sem dono.
    """
    if not run_id or not step_id or seconds <= 0:
        return
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            UPDATE run_steps SET waiting_seconds = waiting_seconds + ?
            WHERE run_id = ? AND step_id = ?
            """,
            (float(seconds), run_id, step_id),
        )
        connection.commit()
    finally:
        connection.close()


def carry_round(run_id: str, step_id: str, *, db_path: Path | None = None) -> float:
    """Fecha a volta do step no relógio e devolve o tempo acumulado até aqui.

    Uma volta nova do laço reabre `started_at`/`ended_at`. Sem guardar antes o
    que a volta anterior gastou, o step voltava a zero a cada rodada — e um
    review que rodou três vezes aparecia com o tempo só da última.

    A duração líquida (parede menos espera) vai para `carried_seconds`, e a
    espera zera junto: ela já foi descontada ali, e descontá-la de novo da volta
    seguinte comeria tempo de trabalho.

    Lido e escrito no banco, e não no `StepRecord`: a espera só existe lá — quem
    a soma é a thread da sessão (ver `add_waiting_seconds`).
    """
    connection = connect(db_path or default_db_path())
    try:
        row = connection.execute(
            """
            SELECT started_at, ended_at, waiting_seconds, carried_seconds
            FROM run_steps WHERE run_id = ? AND step_id = ?
            """,
            (run_id, step_id),
        ).fetchone()
        if row is None:
            return 0.0
        carried = float(row["carried_seconds"] or 0.0)
        carried += _net_seconds(
            str(row["started_at"] or ""),
            str(row["ended_at"] or ""),
            float(row["waiting_seconds"] or 0.0),
        )
        connection.execute(
            """
            UPDATE run_steps
            SET carried_seconds = ?, waiting_seconds = 0, started_at = '', ended_at = ''
            WHERE run_id = ? AND step_id = ?
            """,
            (carried, run_id, step_id),
        )
        connection.commit()
        return carried
    finally:
        connection.close()


def _net_seconds(started_at: str, ended_at: str, waiting_seconds: float) -> float:
    """Parede menos espera; zero quando a volta não tem começo e fim gravados."""
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(ended_at)
    except ValueError:
        return 0.0
    return max(0.0, (end - start).total_seconds() - max(0.0, waiting_seconds))


def delete_run(run_id: str, *, db_path: Path | None = None) -> bool:
    """Apaga a run e tudo que pendura nela. `False` = não existia.

    Steps, eventos e artefatos vão junto por `ON DELETE CASCADE` — o que fica no
    disco do workspace não é nosso para apagar: o Pulse grava caminho, não
    arquivo.
    """
    connection = connect(db_path or default_db_path())
    try:
        cursor = connection.execute("DELETE FROM runs WHERE id = ?", (run_id,))
        connection.commit()
        return cursor.rowcount > 0
    finally:
        connection.close()


def delete_step(run_id: str, step_id: str, *, db_path: Path | None = None) -> None:
    """Tira um step da run.

    Existe para o fan-out: o step que vira N some, e no lugar dele entram os N.
    Deixar o original viraria uma linha a mais no painel, sem dono.
    """
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            "DELETE FROM run_steps WHERE run_id = ? AND step_id = ?", (run_id, step_id)
        )
        connection.commit()
    finally:
        connection.close()


def record_event(
    run_id: str,
    *,
    kind: str,
    title: str,
    detail: str = "",
    step_id: str = "",
    acp_session_id: str = "",
    tool_id: str = "",
    db_path: Path | None = None,
) -> None:
    """Grava uma linha do log. Um `tool_id` repetido atualiza a linha existente."""
    if not run_id or not (title or detail):
        return
    connection = connect(db_path or default_db_path())
    try:
        row = None
        if tool_id:
            row = connection.execute(
                """
                SELECT id FROM run_events
                WHERE run_id = ? AND acp_session_id = ? AND tool_id = ?
                """,
                (run_id, acp_session_id, tool_id),
            ).fetchone()
        if row is not None:
            connection.execute(
                "UPDATE run_events SET title = ?, detail = ? WHERE id = ?",
                (title[:300], detail[:MAX_DETAIL], int(row["id"])),
            )
        else:
            connection.execute(
                """
                INSERT INTO run_events
                  (run_id, step_id, acp_session_id, kind, title, detail, tool_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    step_id,
                    acp_session_id,
                    kind,
                    title[:300],
                    detail[:MAX_DETAIL],
                    tool_id,
                    utc_now(),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def list_events(run_id: str, *, db_path: Path | None = None) -> list[dict[str, str]]:
    if not run_id:
        return []
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            """
            SELECT step_id, kind, title, detail, tool_id, acp_session_id
            FROM run_events WHERE run_id = ? ORDER BY id
            """,
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "step_id": str(row["step_id"] or ""),
            "kind": str(row["kind"] or ""),
            "title": str(row["title"] or ""),
            "detail": str(row["detail"] or ""),
            "tool_id": str(row["tool_id"] or ""),
            "acp_session_id": str(row["acp_session_id"] or ""),
        }
        for row in rows
    ]


def record_artifact(
    run_id: str,
    path: str,
    *,
    step_id: str = "",
    db_path: Path | None = None,
) -> None:
    if not run_id or not path.strip():
        return
    connection = connect(db_path or default_db_path())
    try:
        connection.execute(
            """
            INSERT INTO run_artifacts (run_id, path, step_id, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(run_id, path) DO NOTHING
            """,
            (run_id, path.strip(), step_id, utc_now()),
        )
        connection.commit()
    finally:
        connection.close()


def list_artifacts(run_id: str, *, db_path: Path | None = None) -> list[dict[str, str]]:
    if not run_id:
        return []
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            "SELECT path, step_id FROM run_artifacts WHERE run_id = ? ORDER BY created_at, path",
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {"path": str(row["path"]), "step_id": str(row["step_id"] or "")}
        for row in rows
    ]


def list_sessions(run_id: str, *, db_path: Path | None = None) -> list[dict[str, str]]:
    """Sessões ACP de cada step, na ordem em que rodaram."""
    connection = connect(db_path or default_db_path())
    try:
        rows = connection.execute(
            """
            SELECT step_id, label, acp_session_id FROM run_steps
            WHERE run_id = ? AND acp_session_id != '' ORDER BY position, step_id
            """,
            (run_id,),
        ).fetchall()
    finally:
        connection.close()
    return [
        {
            "step_id": str(row["step_id"]),
            "label": str(row["label"] or row["step_id"]),
            "acp_session_id": str(row["acp_session_id"]),
        }
        for row in rows
    ]
