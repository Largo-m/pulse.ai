from __future__ import annotations

from pathlib import Path

REFERENCE_ALIASES: dict[str, str] = {
    "create-prd": "@references /create-prd/SKILL.md",
    "create-techspec": "@references /create-techspec/SKILL.md",
    "create-tasks": "@references /create-tasks/SKILL.md",
    "execute-task": "@references /execute-task/SKILL.md",
}


def resolve_reference(reference: str) -> str:
    return REFERENCE_ALIASES.get(reference, reference)


def build_prompt(user_prompt: str, reference: str) -> str:
    resolved = resolve_reference(reference)
    body = user_prompt.strip()
    if not body:
        raise ValueError("prompt não pode ser vazio")
    return f"{resolved}\n\n{body}"


def augment_workflow_paths(
    prompt: str,
    *,
    project_path: Path,
    artifacts_path: Path,
) -> str:
    return (
        f"{prompt.rstrip()}\n\n"
        f"Repositório alvo (explorar código e contexto): `{project_path}`\n"
        f"Repositório de artefatos (salvar PRD, TechSpec e ADRs): `{artifacts_path}`\n"
        f"Use `{artifacts_path}/.workflow/tasks/<slug>/` como diretório de artefatos."
    )


def build_techspec_prompt(
    *,
    project_path: Path,
    artifacts_path: Path,
    prd_path: Path,
    reference: str = "create-techspec",
) -> str:
    resolved = resolve_reference(reference)

    try:
        relative_prd = prd_path.relative_to(artifacts_path)
    except ValueError:
        relative_prd = prd_path

    slug = prd_path.parent.name
    task_dir = artifacts_path / ".workflow" / "tasks" / slug

    body = (
        f"Siga o fluxo completo da skill, incluindo exploração do código, "
        f"perguntas técnicas de clarificação (3–6, uma por vez) conforme "
        f"`references/question-protocol.md`, ADRs, rascunho e revisão com aprovação.\n"
        f"PRD de entrada: `{relative_prd.as_posix()}`\n"
        f"Repositório alvo (explorar código): `{project_path}`\n"
        f"Repositório de artefatos: `{artifacts_path}`\n"
        f"Diretório da tarefa: `{task_dir}/`\n"
        f"Leia o PRD em `{prd_path}` e os ADRs em `{task_dir}/adrs/` antes de iniciar.\n"
        f"NÃO escreva `{task_dir}/_techspec.md` até o usuário aprovar o rascunho final."
    )
    return f"{resolved}\n\n{body}"


def resolve_prd_path(artifacts_path: Path, input_file: str) -> Path:
    return _resolve_input_artifact(
        artifacts_path,
        input_file,
        label="PRD",
        expected_suffix="_prd.md",
    )


def resolve_techspec_path(artifacts_path: Path, input_file: str) -> Path:
    return _resolve_input_artifact(
        artifacts_path,
        input_file,
        label="TechSpec",
        expected_suffix="_techspec.md",
    )


def resolve_master_tasks_path_for_execute(artifacts_path: Path, input_file: str) -> Path:
    from cursor_task.task_tracker import resolve_master_tasks_path

    return resolve_master_tasks_path(artifacts_path, input_file)


def build_tasks_prompt(
    *,
    project_path: Path,
    artifacts_path: Path,
    techspec_path: Path,
    reference: str = "create-tasks",
) -> str:
    resolved = resolve_reference(reference)

    try:
        relative_techspec = techspec_path.relative_to(artifacts_path)
    except ValueError:
        relative_techspec = techspec_path

    task_dir = techspec_path.parent
    prd_path = task_dir / "_prd.md"
    prd_note = (
        f"Leia também o PRD em `{prd_path}`.\n"
        if prd_path.exists()
        else "O PRD não foi encontrado; derive requisitos comportamentais a partir do TechSpec.\n"
    )

    body = (
        f"Siga o fluxo completo da skill, incluindo exploração do código, "
        f"decomposição em tasks, aprovação interativa do breakdown, "
        f"geração de arquivos individuais e enriquecimento de cada task.\n"
        f"TechSpec de entrada: `{relative_techspec.as_posix()}`\n"
        f"Repositório alvo (explorar código): `{project_path}`\n"
        f"Repositório de artefatos: `{artifacts_path}`\n"
        f"Diretório da tarefa: `{task_dir}/`\n"
        f"Leia o TechSpec em `{techspec_path}`.\n"
        f"{prd_note}"
        f"Leia os ADRs em `{task_dir}/adrs/` antes de iniciar.\n"
        f"Use `references/task-template.md` e `references/task-context-schema.md` da skill.\n"
        f"NÃO escreva `{task_dir}/_tasks.md` nem `task_NN.md` até o usuário aprovar o breakdown final.\n"
        f"Após apresentar o breakdown, encerre com revisão explícita e opções:\n"
        f"**A)** Aprovado — gerar `_tasks.md` e `task_NN.md` com enriquecimento completo\n"
        f"**B)** Ajustar breakdown (descrever mudanças)\n"
        f"**C)** Revisar escopo, complexidade ou dependências\n"
        f"**D)** Descartar e recomeçar\n"
        f"Aguarde a resposta do usuário antes de gravar qualquer arquivo."
    )
    return f"{resolved}\n\n{body}"


def build_execute_task_prompt(
    *,
    project_path: Path,
    artifacts_path: Path,
    task_dir: Path,
    task_file: Path,
    master_tasks_path: Path,
    auto_commit: bool,
    reference: str = "execute-task",
) -> str:
    resolved = resolve_reference(reference)
    commit_mode = "enabled" if auto_commit else "disabled"

    try:
        relative_task = task_file.relative_to(artifacts_path)
    except ValueError:
        relative_task = task_file

    try:
        relative_master = master_tasks_path.relative_to(artifacts_path)
    except ValueError:
        relative_master = master_tasks_path

    prd_path = task_dir / "_prd.md"
    techspec_path = task_dir / "_techspec.md"
    prd_note = (
        f"Leia o PRD em `{prd_path}`.\n"
        if prd_path.exists()
        else ""
    )

    body = (
        f"Siga o fluxo completo da skill execute-task.\n"
        f"Task specification: `{relative_task.as_posix()}`\n"
        f"PRD directory: `{task_dir}/`\n"
        f"Master tasks file: `{relative_master.as_posix()}`\n"
        f"Task file path: `{task_file}`\n"
        f"Repositório alvo (implementar código): `{project_path}`\n"
        f"Repositório de artefatos: `{artifacts_path}`\n"
        f"Leia o TechSpec em `{techspec_path}`.\n"
        f"{prd_note}"
        f"Leia os ADRs em `{task_dir}/adrs/` antes de iniciar.\n"
        f"Auto-commit mode: {commit_mode}\n"
        f"Esta execução roda em contexto isolado (novo chat) — implemente apenas esta task.\n"
        f"Ao concluir, atualize tracking conforme `references/tracking-checklist.md` "
        f"e marque status como completed no task file e em `_tasks.md`."
    )
    return f"{resolved}\n\n{body}"


def _resolve_input_artifact(
    artifacts_path: Path,
    input_file: str,
    *,
    label: str,
    expected_suffix: str,
) -> Path:
    path = Path(input_file).expanduser()
    if not path.is_absolute():
        path = artifacts_path / path
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"{label} não encontrado: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} deve ser um arquivo: {path}")
    if not path.name.endswith(expected_suffix):
        raise ValueError(f"{label} deve ser um arquivo {expected_suffix}: {path}")
    return path
