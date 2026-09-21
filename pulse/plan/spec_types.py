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

LEGACY_SPEC_TYPES: tuple[SpecType, ...] = (
    SpecType("new-issue", "New issue", "Nova feature"),
    SpecType("fix-bug", "Fix / bug", "Quick fix"),
)

ALL_SPEC_TYPES: tuple[SpecType, ...] = SPEC_TYPES + LEGACY_SPEC_TYPES
SPEC_TYPE_IDS = tuple(spec_type.id for spec_type in SPEC_TYPES)
ALL_SPEC_TYPE_IDS = tuple(spec_type.id for spec_type in ALL_SPEC_TYPES)
LEGACY_SPEC_TYPE_IDS = tuple(spec_type.id for spec_type in LEGACY_SPEC_TYPES)


def get_spec_type(spec_id: str) -> SpecType | None:
    for spec_type in ALL_SPEC_TYPES:
        if spec_type.id == spec_id:
            return spec_type
    return None


def is_runnable_spec_type(spec_id: str) -> bool:
    return spec_id in ALL_SPEC_TYPE_IDS
