"""O pouco de git que o Pulse precisa saber.

O Pulse não versiona nada e não lê diff: o que ele faz aqui é abrir um lugar
isolado para a run trabalhar (`git worktree`) e perguntar em que branch isso
está acontecendo. Nada além disso — merge, push e revisão continuam sendo
trabalho de quem usa o git.

É o git CLI por `subprocess`, não uma biblioteca: a única operação de escrita é
`worktree add`, e carregar uma dependência inteira por ela seria caro para quem
nem liga a chave.

Leitura nunca levanta — projeto fora de repositório, git ausente do PATH ou HEAD
destacado devolvem vazio, e a sessão segue sem branch. Escrita levanta
(`GitError`): é melhor a run não começar do que começar no diretório errado.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

#: Teto de cada comando. Nenhum dos que rodam aqui é demorado; o prazo existe
#: para um git travado (credential helper, lock de index) não segurar a run.
TIMEOUT = 15.0

#: Até onde `add_worktree` tenta desambiguar um nome de branch já existente.
#: Depois disso o problema não é colisão de nome, e inventar sufixo sem fim só
#: esconderia isso.
MAX_BRANCH_ATTEMPTS = 20


class GitError(RuntimeError):
    """Comando git que falhou e cujo resultado ninguém pode ignorar."""


def _run(args: list[str], *, cwd: Path | str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )


def _read(args: list[str], *, cwd: Path | str) -> str:
    """Saída de um comando de leitura. Qualquer tropeço vira string vazia."""
    try:
        result = _run(args, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        # git ausente do PATH, diretório que sumiu, prazo estourado: nenhum
        # deles é motivo para a run não acontecer.
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _write(args: list[str], *, cwd: Path | str) -> str:
    try:
        result = _run(args, cwd=cwd)
    except (OSError, subprocess.SubprocessError) as error:
        raise GitError(f"git {' '.join(args)}: {error}") from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise GitError(f"git {' '.join(args)}: {detail or 'falhou'}")
    return result.stdout.strip()


def repo_root(path: Path | str) -> Path | None:
    """Raiz do repositório que contém `path`, ou `None` se não houver."""
    candidate = Path(path)
    if not candidate.exists():
        return None
    top = _read(["rev-parse", "--show-toplevel"], cwd=candidate)
    if not top:
        return None
    return Path(top).resolve()


def is_repo(path: Path | str) -> bool:
    return repo_root(path) is not None


def current_branch(path: Path | str) -> str:
    """Branch atual, ou vazio em HEAD destacado e fora de repositório.

    Vazio e não o sha: a tela mostra isto ao lado do modelo, e um sha solto ali
    pareceria nome de branch para quem só bate o olho.
    """
    candidate = Path(path)
    if not candidate.exists():
        return ""
    name = _read(["rev-parse", "--abbrev-ref", "HEAD"], cwd=candidate)
    return "" if name == "HEAD" else name


def branch_exists(repo: Path | str, branch: str) -> bool:
    if not branch:
        return False
    try:
        result = _run(
            ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=repo
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def add_worktree(
    repo: Path | str,
    path: Path | str,
    branch: str,
    *,
    start: str = "HEAD",
) -> str:
    """Abre um worktree em `path`, numa branch nova, e devolve o nome dela.

    O nome pedido pode já existir — uma run anterior cujo worktree foi removido
    deixa a branch para trás. Em vez de falhar ou reaproveitar (o que faria duas
    runs escreverem no mesmo histórico), o nome ganha sufixo: `…-2`, `…-3`.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    prune_worktrees(repo)
    name = branch
    for attempt in range(2, MAX_BRANCH_ATTEMPTS + 2):
        if not branch_exists(repo, name):
            break
        name = f"{branch}-{attempt}"
    else:
        raise GitError(f"não consegui um nome de branch livre a partir de `{branch}`")
    _write(["worktree", "add", "-b", name, str(target), start], cwd=repo)
    return name


def attach_worktree(repo: Path | str, path: Path | str, branch: str) -> None:
    """Reabre um worktree em `path` numa branch que já existe.

    É o caminho da run retomada que perdeu o diretório: o trabalho dos steps que
    já fecharam está commitado na branch dela, e uma branch nova a partir do HEAD
    deixaria esse trabalho de fora.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    prune_worktrees(repo)
    _write(["worktree", "add", str(target), branch], cwd=repo)


def prune_worktrees(repo: Path | str) -> None:
    """Esquece worktrees cujo diretório sumiu do disco.

    Diretório apagado à mão continua registrado no git, e `worktree add` recusa
    o mesmo caminho até alguém rodar `prune`. Falhar aqui não impede nada: o
    `add` seguinte reporta o erro de verdade.
    """
    _read(["worktree", "prune"], cwd=repo)


def remove_worktree(repo: Path | str, path: Path | str, *, force: bool = False) -> None:
    """Desfaz o worktree. Sem `force`, git recusa se houver mudança não salva."""
    args = ["worktree", "remove"]
    if force:
        args.append("--force")
    args.append(str(path))
    _write(args, cwd=repo)


def has_changes(path: Path | str) -> bool:
    """Há trabalho não commitado aqui? Na dúvida, `True`.

    Quem pergunta está prestes a apagar o diretório. Um erro de leitura não pode
    virar "não tem nada aqui".
    """
    candidate = Path(path)
    if not candidate.exists():
        return False
    try:
        result = _run(["status", "--porcelain"], cwd=candidate)
    except (OSError, subprocess.SubprocessError):
        return True
    if result.returncode != 0:
        return True
    return bool(result.stdout.strip())


def git_available() -> bool:
    try:
        result = subprocess.run(  # noqa: S603
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


__all__ = [
    "GitError",
    "add_worktree",
    "attach_worktree",
    "branch_exists",
    "current_branch",
    "git_available",
    "has_changes",
    "is_repo",
    "prune_worktrees",
    "remove_worktree",
    "repo_root",
]
