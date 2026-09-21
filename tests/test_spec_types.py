from pulse.plan.spec_types import (
    ALL_SPEC_TYPE_IDS,
    SPEC_TYPE_IDS,
    SPEC_TYPES,
    get_spec_type,
    is_runnable_spec_type,
)


def test_spec_types_defined():
    assert len(SPEC_TYPES) == 3
    assert SPEC_TYPE_IDS == (
        "spec",
        "setup-project",
        "analyze-codebase",
    )
    assert "new-issue" in ALL_SPEC_TYPE_IDS
    assert "fix-bug" in ALL_SPEC_TYPE_IDS


def test_get_spec_type():
    spec_type = get_spec_type("spec")
    assert spec_type is not None
    assert spec_type.label == "Nova spec"
    assert get_spec_type("fix-bug") is not None
    assert get_spec_type("new-issue") is not None
    assert get_spec_type("unknown") is None
    assert is_runnable_spec_type("spec")
    assert is_runnable_spec_type("fix-bug")
    assert not is_runnable_spec_type("unknown")
