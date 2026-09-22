from pulse.plan.spec_types import SPEC_TYPE_IDS, SPEC_TYPES, get_spec_type


def test_spec_types_defined():
    assert len(SPEC_TYPES) == 3
    assert SPEC_TYPE_IDS == (
        "spec",
        "setup-project",
        "analyze-codebase",
    )


def test_get_spec_type():
    spec_type = get_spec_type("spec")
    assert spec_type is not None
    assert spec_type.label == "Nova spec"
    assert get_spec_type("fix-bug") is None
    assert get_spec_type("new-issue") is None
    assert get_spec_type("unknown") is None
