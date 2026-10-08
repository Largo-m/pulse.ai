from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from pulse.domain import ui_text

# Labels and model names are single-line display text.
_LABELS = (
    st.text(st.characters(exclude_categories=("Cc", "Zl", "Zp")), min_size=1)
    .map(str.strip)
    .filter(bool)
)


@given(label=_LABELS, turn=st.integers(min_value=2, max_value=999))
def test_a_continuation_title_reads_back_as_its_phase_label(label: str, turn: int) -> None:
    """The sidebar groups continuation turns under their step by this read-back;
    if the producer's wording drifts from the reader, turns land on no step."""
    assert ui_text.phase_label_of(ui_text.continuation_label(label, turn)) == label


def test_a_plain_phase_title_is_its_own_label() -> None:
    """Only the continuation suffix is stripped; a first-turn title is untouched."""
    assert ui_text.phase_label_of("Review — round 2") == "Review — round 2"


@given(model=_LABELS)
def test_a_model_notice_reads_back_as_its_model(model: str) -> None:
    """The cockpit header shows the model by reading this notice back."""
    assert ui_text.model_of_notice(ui_text.model_notice(model)) == model


def test_a_title_that_is_not_a_model_notice_names_no_model() -> None:
    """Any other session title must not overwrite the model shown."""
    assert ui_text.model_of_notice("Plan ready") is None
