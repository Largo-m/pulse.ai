"""`ContextUsage` reads the agent's `usage_update`; anything else is not a reading.

The payload is agent output, untrusted: a malformed field must not invent a
number on screen, and a well-formed one must reach it unchanged.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from pulse.history.events import ContextUsage, PhaseItem, PhaseStatus, format_tokens


def test_a_usage_update_is_read_as_the_tokens_in_context():
    usage = ContextUsage.parse({"sessionUpdate": "usage_update", "used": 42000, "size": 200000})

    assert usage == ContextUsage(used=42000)


@pytest.mark.parametrize(
    "update",
    [
        {"sessionUpdate": "usage_update"},
        {"sessionUpdate": "usage_update", "used": -1, "size": 200000},
        {"sessionUpdate": "usage_update", "used": True, "size": 200000},
        {"sessionUpdate": "usage_update", "used": "42000", "size": 200000},
        {"sessionUpdate": "usage_update", "used": 4.2, "size": 200000},
        {"sessionUpdate": "usage_update", "used": None},
    ],
)
def test_an_update_without_a_valid_used_count_is_not_a_reading(update):
    assert ContextUsage.parse(update) is None


@given(used=st.integers(min_value=0))
def test_any_well_formed_reading_survives_parsing(used):
    assert ContextUsage.parse({"used": used}) == ContextUsage(used=used)


@pytest.mark.parametrize(
    ("tokens", "label"),
    [
        (0, "0"),
        (999, "999"),
        (1000, "1k"),
        (42_499, "42k"),
        (999_999, "999k"),
        (1_000_000, "1.0M"),
        (1_250_000, "1.2M"),
    ],
)
def test_token_counts_read_in_a_narrow_column(tokens, label):
    assert format_tokens(tokens) == label


def test_a_restarted_step_forgets_its_context():
    """A rerun opens a fresh ACP session; the old reading would overstate it."""
    phase = PhaseItem(id="build", label="Build", status=PhaseStatus.RUNNING, started_at=1.0)
    phase.context = ContextUsage(used=10)

    phase.restart()

    assert phase.context is None
