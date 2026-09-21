from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SpecType:
    id: str
    label: str
    description: str


SPEC_TYPES: tuple[SpecType, ...] = (
    SpecType("spec", "Nova spec", "O Pulse escolhe o flow"),
    SpecType("setup-project", "Setup project", "Setup inicial"),
    SpecType("analyze-codebase", "Analyze codebase", "Mapear código"),
)

SPEC_TYPE_IDS = tuple(spec_type.id for spec_type in SPEC_TYPES)


def get_spec_type(spec_id: str) -> SpecType | None:
    for spec_type in SPEC_TYPES:
        if spec_type.id == spec_id:
            return spec_type
    return None
