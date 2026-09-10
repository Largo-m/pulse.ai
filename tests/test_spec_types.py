from pulse.plan.spec_types import SPEC_TYPE_IDS, SPEC_TYPES, get_spec_type


def test_spec_types_defined():
    assert len(SPEC_TYPES) == 4
    assert SPEC_TYPE_IDS == (
        "new-issue",
        "fix-bug",
        "setup-project",
        "analyze-codebase",
    )


def test_get_spec_type():
    spec_type = get_spec_type("fix-bug")
    assert spec_type is not None
    assert spec_type.label == "Fix / bug"
    assert get_spec_type("unknown") is None
