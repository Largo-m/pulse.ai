from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecType:
    id: str
    label: str
    description: str


SPEC_TYPES: tuple[SpecType, ...] = (
    SpecType("new-issue", "New issue", "Nova funcionalidade ou melhoria"),
    SpecType("fix-bug", "Fix / bug", "Quick mode — bug fix, config ou ajuste pontual (≤3 arquivos)"),
    SpecType("setup-project", "Setup project", "Bootstrap ou configuração inicial"),
    SpecType("analyze-codebase", "Analyze codebase", "Mapear e entender o código existente"),
)

SPEC_TYPE_IDS = tuple(spec_type.id for spec_type in SPEC_TYPES)


def get_spec_type(spec_id: str) -> SpecType | None:
    for spec_type in SPEC_TYPES:
        if spec_type.id == spec_id:
            return spec_type
    return None
