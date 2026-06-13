from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_PHASE_DIR_PATTERN = re.compile(r"^(\d{2})-(.+)$")


@dataclass(frozen=True)
class SpecPhase:
    number: int
    slug: str
    name: str
    directory: Path
    product_path: Path
    technical_path: Path


def resolve_specs_root(artifacts_path: Path) -> Path:
    return artifacts_path / "docs" / "specs"


def discover_phases(
    specs_root: Path,
    *,
    from_phase: int | None = None,
    to_phase: int | None = None,
    only: list[str] | None = None,
) -> list[SpecPhase]:
    phases_dir = specs_root / "phases"
    if not phases_dir.is_dir():
        raise FileNotFoundError(f"diretório de fases não encontrado: {phases_dir}")

    phases: list[SpecPhase] = []
    for entry in sorted(phases_dir.iterdir()):
        if not entry.is_dir():
            continue
        match = _PHASE_DIR_PATTERN.match(entry.name)
        if not match:
            continue

        number = int(match.group(1))
        name = match.group(2)
        product_path = entry / "product.md"
        technical_path = entry / "technical.md"
        if not product_path.is_file() or not technical_path.is_file():
            continue

        phases.append(
            SpecPhase(
                number=number,
                slug=entry.name,
                name=name,
                directory=entry,
                product_path=product_path,
                technical_path=technical_path,
            )
        )

    phases.sort(key=lambda phase: phase.number)

    if only:
        allowed = {slug.strip() for slug in only}
        phases = [phase for phase in phases if phase.slug in allowed or phase.name in allowed]

    if from_phase is not None:
        phases = [phase for phase in phases if phase.number >= from_phase]
    if to_phase is not None:
        phases = [phase for phase in phases if phase.number <= to_phase]

    if not phases:
        raise ValueError("nenhuma fase de spec encontrada com os filtros informados")

    return phases


def phase_branch_name(branch_prefix: str, phase: SpecPhase) -> str:
    prefix = branch_prefix.strip().rstrip("/")
    return f"{prefix}/{phase.slug}"


def validate_branch_namespace(root_parent: str, branch_prefix: str) -> None:
    root = root_parent.strip().rstrip("/")
    prefix = branch_prefix.strip().rstrip("/")
    if prefix == root or prefix.startswith(f"{root}/"):
        raise ValueError(
            f"branch_prefix '{prefix}' conflita com parent_branch '{root}': "
            f"git não permite criar refs filhas quando a branch pai já existe. "
            f"use um prefixo diferente (ex.: feat/pulse-specs)."
        )


def phases_by_number(phases: list[SpecPhase]) -> dict[int, SpecPhase]:
    return {phase.number: phase for phase in phases}


def resolve_initial_parent_branch(
    root_parent: str,
    branch_prefix: str,
    first_phase: SpecPhase,
    index: dict[int, SpecPhase],
) -> str:
    if first_phase.number <= 1:
        return root_parent.strip().rstrip("/")
    previous = index.get(first_phase.number - 1)
    if previous is None:
        raise ValueError(
            f"fase anterior à {first_phase.slug} (número {first_phase.number - 1}) não encontrada"
        )
    return phase_branch_name(branch_prefix, previous)
