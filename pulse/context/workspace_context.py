from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RULE_FILENAMES = ("AGENTS.md", "CLAUDE.md")
RULE_DIR_NAMES = (".cursor/rules",)
_SKILL_FILENAME = "SKILL.md"
_SKILL_SEARCH_SKIP_DIRS = {
    ".git",
    ".pulse",
    ".venv",
    "node_modules",
    "venv",
    "dist",
    "build",
    "__pycache__",
}
_RULE_EXTENSIONS = {".md", ".mdc"}
_DEFAULT_RULE_INLINE_BUDGET = 16_000
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)
_NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class WorkspaceRule:
    relative_path: str
    content: str


@dataclass(frozen=True)
class WorkspaceSkill:
    name: str
    description: str
    skill_file: str


@dataclass(frozen=True)
class WorkspaceContext:
    workspace: Path
    rules: tuple[WorkspaceRule, ...]
    skills: tuple[WorkspaceSkill, ...]


def load_workspace_context(workspace: Path) -> WorkspaceContext:
    return WorkspaceContext(
        workspace=workspace,
        rules=tuple(discover_workspace_rules(workspace)),
        skills=tuple(discover_workspace_skills(workspace)),
    )


def discover_workspace_rules(workspace: Path) -> list[WorkspaceRule]:
    rules: list[WorkspaceRule] = []
    seen: set[str] = set()

    for filename in RULE_FILENAMES:
        path = workspace / filename
        if path.is_file():
            relative = path.relative_to(workspace).as_posix()
            if relative not in seen:
                seen.add(relative)
                rules.append(
                    WorkspaceRule(
                        relative_path=relative,
                        content=path.read_text(encoding="utf-8"),
                    )
                )

    for rule_dir_name in RULE_DIR_NAMES:
        rules_dir = workspace / rule_dir_name
        if not rules_dir.is_dir():
            continue
        for path in sorted(rules_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in _RULE_EXTENSIONS:
                continue
            relative = path.relative_to(workspace).as_posix()
            if relative in seen:
                continue
            seen.add(relative)
            rules.append(
                WorkspaceRule(
                    relative_path=relative,
                    content=path.read_text(encoding="utf-8"),
                )
            )

    return rules


def discover_workspace_skills(workspace: Path) -> list[WorkspaceSkill]:
    skills: list[WorkspaceSkill] = []
    seen: set[str] = set()

    for skill_file in sorted(workspace.rglob(_SKILL_FILENAME)):
        if not skill_file.is_file():
            continue
        if _should_skip_skill_path(skill_file, workspace):
            continue
        relative = skill_file.relative_to(workspace).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        name, description = parse_skill_metadata(skill_file)
        skills.append(
            WorkspaceSkill(
                name=name,
                description=description,
                skill_file=relative,
            )
        )

    return skills


def _should_skip_skill_path(skill_file: Path, workspace: Path) -> bool:
    try:
        parts = skill_file.relative_to(workspace).parts
    except ValueError:
        return True
    return any(part in _SKILL_SEARCH_SKIP_DIRS for part in parts)


def parse_skill_metadata(skill_file: Path) -> tuple[str, str]:
    text = skill_file.read_text(encoding="utf-8")
    name = skill_file.parent.name
    description = ""

    match = _FRONTMATTER_RE.match(text)
    if match:
        frontmatter = match.group(1)
        name_match = _NAME_RE.search(frontmatter)
        if name_match:
            name = name_match.group(1).strip().strip("\"'")
        description_match = _DESCRIPTION_RE.search(frontmatter)
        if description_match:
            description = description_match.group(1).strip().strip("\"'")

    if not description:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and stripped != "---":
                description = stripped[:240]
                break

    return name, description


def extend_prompt_with_workspace_context(
    sections: list[str],
    workspace: Path,
    *,
    rule_inline_budget: int = _DEFAULT_RULE_INLINE_BUDGET,
) -> None:
    context = load_workspace_context(workspace)
    sections.extend(format_workspace_context_sections(context, rule_inline_budget=rule_inline_budget))


def format_workspace_context_sections(
    context: WorkspaceContext,
    *,
    rule_inline_budget: int = _DEFAULT_RULE_INLINE_BUDGET,
) -> list[str]:
    sections = [
        "## Regras e contexto do projeto",
        "",
        "Leia `AGENTS.md` e `CLAUDE.md` no workspace (se existirem) **antes de editar código**.",
        "Siga também todas as regras adicionais listadas abaixo.",
        "",
    ]

    if context.rules:
        sections.extend(
            [
                "### Arquivos de regras do projeto",
                "",
            ]
        )
        for rule in context.rules:
            sections.append(f"- `{rule.relative_path}`")
        sections.append("")

        remaining = rule_inline_budget
        inlined: list[WorkspaceRule] = []
        for rule in context.rules:
            if remaining <= 0:
                break
            if len(rule.content) <= remaining:
                inlined.append(rule)
                remaining -= len(rule.content)

        if inlined:
            sections.extend(
                [
                    "Conteúdo das regras (leia e aplique; arquivos truncados devem ser lidos no disco):",
                    "",
                ]
            )
            for rule in inlined:
                sections.extend(
                    [
                        f"#### {rule.relative_path}",
                        rule.content.strip(),
                        "",
                    ]
                )

        if len(inlined) < len(context.rules):
            sections.extend(
                [
                    "Leia no disco **todos** os arquivos de regras acima que não foram inlined "
                    "antes de criar ou editar arquivos.",
                    "",
                ]
            )
    else:
        sections.extend(
            [
                "Nenhum arquivo de regras foi encontrado além dos padrões `AGENTS.md` / `CLAUDE.md`. "
                "Se existirem, leia-os no workspace antes de editar.",
                "",
            ]
        )

    sections.extend(format_workspace_skills_section(context.skills))
    return sections


def format_workspace_skills_section(skills: tuple[WorkspaceSkill, ...]) -> list[str]:
    sections = [
        "### Skills do projeto (sob demanda)",
        "",
        "Skills são recursos especializados. Quando uma skill for relevante para a tarefa, "
        "**leia o arquivo `SKILL.md` correspondente antes de agir**, assim como agentes LLM fazem.",
        "",
    ]

    if not skills:
        sections.extend(
            [
                "Nenhum arquivo `SKILL.md` foi encontrado no workspace.",
                "",
            ]
        )
        return sections

    for skill in skills:
        sections.extend(
            [
                f"- **{skill.name}** — `{skill.skill_file}`",
                f"  {skill.description or 'Sem descrição.'}",
                "",
            ]
        )

    sections.extend(
        [
            "Não carregue todas as skills de uma vez. Leia apenas a `SKILL.md` necessária para o passo atual.",
            "",
        ]
    )
    return sections
