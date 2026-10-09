"""Prompt templates: run values fill `{{key}}`, and a missing value is an error."""

from __future__ import annotations

import pytest

from pulse.orchestrator.render import TemplateError, render


def test_placeholders_are_filled_with_their_values():
    assert render("Do {{ task }} in {{workspace}}.", {"task": "x", "workspace": "/w"}) == (
        "Do x in /w."
    )


def test_a_conditional_keeps_its_body_only_when_the_value_has_text():
    template = "A\n{{#if notes}}Notes: {{notes}}\n{{/if}}B"

    assert render(template, {"notes": "read me"}) == "A\nNotes: read me\nB"
    assert render(template, {"notes": "  "}) == "A\nB"


def test_a_conditional_on_a_value_the_run_does_not_have_drops_its_body():
    """Optional sections may name values a run lacks; that is not an error."""
    assert render("A {{#if absent}}hidden {{absent}}{{/if}}B", {}) == "A B"


def test_every_missing_key_is_named_once_and_sorted():
    with pytest.raises(TemplateError) as raised:
        render("{{zeta}} {{alpha}} {{zeta}}", {})

    assert str(raised.value) == "placeholder without a value: alpha, zeta"
