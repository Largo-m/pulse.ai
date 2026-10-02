from __future__ import annotations

import os
from pathlib import Path

GLOBAL_CONFIG_DIR = Path.home() / ".pulse"
GLOBAL_DB_FILE = GLOBAL_CONFIG_DIR / "pulse.db"
GLOBAL_CONFIG_FILE = GLOBAL_DB_FILE

LEGACY_GLOBAL_CONFIG_DIR = Path.home() / ".dev-orchestrator"
LEGACY_GLOBAL_CONFIG_FILE = LEGACY_GLOBAL_CONFIG_DIR / "config.toml"

PROJECT_CONFIG_DIRNAME = ".pulse"
PROJECT_CONFIG_FILENAME = "pulse.db"


def global_state_dir() -> Path:
    home = os.environ.get("PULSE_HOME")
    if home:
        return Path(home).expanduser()
    db_override = os.environ.get("PULSE_DB")
    if db_override:
        return Path(db_override).expanduser().resolve().parent
    return GLOBAL_CONFIG_DIR


def safe_cwd() -> Path:
    """O diretório atual, ou o estado do Pulse quando não dá para lê-lo.

    `os.getcwd()` não é infalível. No macOS ele devolve `EPERM` quando o
    processo está parado dentro de uma pasta protegida — a Lixeira é a comum:
    basta alguém apagar o projeto de onde o engine subiu. Some com `ENOENT`
    quando a pasta foi removida de vez. Quem tropeça nisto é o daemon: ele vive
    destacado, com o cwd que herdou de quem o iniciou, e esse diretório pode
    desaparecer debaixo dele semanas depois.

    O fallback é `~/.pulse` e não um palpite de projeto: nenhum workspace mora
    ali, então quem usava o cwd para descobrir o projeto não descobre nada e cai
    no caminho de "sem projeto", que já existe. É pior do que acertar e muito
    melhor do que levantar — a run morria antes do primeiro step.
    """
    try:
        return Path.cwd()
    except OSError:
        return global_state_dir()


def global_agents_dir() -> Path:
    return global_state_dir() / "agents"


def worktrees_dir() -> Path:
    """Onde ficam os worktrees das runs — fora do repositório, de propósito.

    Dentro do projeto exigiria `.gitignore` de quem nunca pediu nada, e um
    worktree aninhado no próprio repo confunde ferramenta que varre a árvore.
    Em `~/.pulse/` ele fica junto do resto do estado do Pulse, e some junto.
    """
    return global_state_dir() / "worktrees"


def project_config_file(root: Path) -> Path:
    return root.resolve()


def find_project_config_file(start: Path | None = None) -> Path | None:
    from pulse.config.project_config import find_project_root

    return find_project_root(start)
