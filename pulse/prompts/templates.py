"""Templates de fase em Markdown, editáveis pelo usuário.

O prompt que chega no agente tem duas metades: o playbook (`AGENT.md`, como
fazer) e as instruções da fase (o que fazer agora). A segunda metade morava no
Python, então quem instalava o Pulse conseguia editar o playbook e não conseguia
tocar na fase — metade do comportamento ficava trancada dentro do venv.

Agora as duas são arquivo. Cada agente carrega os seus templates ao lado do
`AGENT.md`, e blocos usados por várias fases (isolamento, aprovação, clarify)
ficam em `shared/`:

    ~/.pulse/agents/prd/AGENT.md          playbook
    ~/.pulse/agents/prd/PHASE.md          instruções da fase
    ~/.pulse/agents/prd/CONTINUATION.md   retomada após o questionário
    ~/.pulse/prompts/shared/isolation.md      bloco comum

A resolução é a mesma dos agentes: o global vence o bundled quando existe, então
editar não é sobrescrito no próximo upgrade e apagar volta ao padrão de fábrica.

Placeholders usam `{{chave}}` — chave simples não serve porque o texto de fase
já contém `{id: T1, title: ...}` literal.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pulse.config.paths import global_agents_dir, global_state_dir

PLACEHOLDER = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}", re.IGNORECASE)

#: `{{#if chave}}…{{/if}}` — o trecho some quando a chave está vazia. Existe para
#: a fase não precisar devolver texto ao Python só porque uma linha é opcional
#: (ex.: "leia TECHSPEC.md" quando o Techspec não foi pulado).
CONDITIONAL = re.compile(
    r"\{\{#if\s+([a-z0-9_]+)\s*\}\}\n?(.*?)\{\{/if\}\}\n?",
    re.IGNORECASE | re.DOTALL,
)

#: Nome dos templates que um agente pode trazer.
PHASE = "PHASE.md"
CONTINUATION = "CONTINUATION.md"


class TemplateError(RuntimeError):
    """Template ausente ou pedindo um valor que o Pulse não tem."""


@dataclass(frozen=True)
class LoadedTemplate:
    text: str
    path: Path
    origin: str  # "global" ou "bundled"


def bundled_agents_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "agents" / "bundled"


def bundled_shared_dir() -> Path:
    return Path(__file__).resolve().parent / "templates" / "shared"


def global_shared_dir() -> Path:
    return global_state_dir() / "prompts" / "shared"


def _candidates(agent_id: str, name: str) -> list[tuple[str, Path]]:
    return [
        ("bundled", bundled_agents_dir() / agent_id / name),
        ("global", global_agents_dir() / agent_id / name),
    ]


def load_template(agent_id: str, name: str = PHASE) -> LoadedTemplate:
    chosen: tuple[str, Path] | None = None
    for origin, path in _candidates(agent_id, name):
        if path.is_file():
            chosen = (origin, path)
    if chosen is None:
        raise TemplateError(
            f"template `{name}` não encontrado para o agente `{agent_id}`. "
            f"Esperado em {global_agents_dir() / agent_id / name} "
            f"ou {bundled_agents_dir() / agent_id / name}."
        )
    origin, path = chosen
    return LoadedTemplate(text=path.read_text(encoding="utf-8"), path=path, origin=origin)


def load_shared(name: str) -> LoadedTemplate:
    filename = name if name.endswith(".md") else f"{name}.md"
    candidates = [
        ("bundled", bundled_shared_dir() / filename),
        ("global", global_shared_dir() / filename),
    ]
    found: tuple[str, Path] | None = None
    for origin, path in candidates:
        if path.is_file():
            found = (origin, path)
    if found is None:
        raise TemplateError(f"bloco compartilhado `{filename}` não encontrado")
    origin, path = found
    return LoadedTemplate(text=path.read_text(encoding="utf-8"), path=path, origin=origin)


def render(text: str, context: dict[str, str]) -> str:
    """Troca `{{chave}}` pelo valor. Chave desconhecida é erro, não buraco.

    Silenciar um placeholder faria o agente receber uma instrução truncada e
    ninguém notaria até a run sair errada.
    """
    missing: list[str] = []

    def _conditional(match: re.Match[str]) -> str:
        key, body = match.group(1), match.group(2)
        return body if context.get(key, "").strip() else ""

    text = CONDITIONAL.sub(_conditional, text)

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            missing.append(key)
            return match.group(0)
        return context[key]

    result = PLACEHOLDER.sub(_replace, text)
    if missing:
        raise TemplateError(
            "placeholder sem valor: " + ", ".join(sorted(set(missing)))
        )
    return result


def render_template(agent_id: str, context: dict[str, str], *, name: str = PHASE) -> str:
    return render(load_template(agent_id, name).text, context)


def render_shared(name: str, context: dict[str, str] | None = None) -> str:
    # Sem o rstrip, cada bloco injetado traria a quebra final do arquivo e
    # abriria uma linha em branco a mais dentro do prompt.
    return render(load_shared(name).text, context or {}).rstrip()


def install_global_templates() -> Path:
    """Copia os blocos compartilhados para o global, sem sobrescrever.

    Os templates por agente são instalados junto com o `AGENT.md`, em
    `pulse.agents.loader.install_global_agents`.
    """
    import shutil

    dest = global_shared_dir()
    source = bundled_shared_dir()
    if source.is_dir():
        dest.mkdir(parents=True, exist_ok=True)
        for item in sorted(source.glob("*.md")):
            if not (dest / item.name).is_file():
                shutil.copy2(item, dest / item.name)
    return dest
