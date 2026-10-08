"""The CI mutation gate counts what the tests caught, not what mutmut merely ran."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import mutation_gate
from scripts.mutation_gate import score


def test_a_timeout_counts_as_caught_and_an_uncovered_mutant_as_missed():
    stats = {"total": 10, "killed": 6, "timeout": 2, "no_tests": 1, "survived": 1, "skipped": 0}

    assert score(stats) == 80.0


def test_skipped_mutants_are_left_out_of_the_score():
    assert score({"total": 10, "killed": 8, "skipped": 2}) == 100.0


@pytest.mark.parametrize(("killed", "code"), [(8, 0), (7, 1)])
def test_the_gate_fails_below_the_floor(tmp_path: Path, monkeypatch, killed: int, code: int):
    stats = tmp_path / "stats.json"
    stats.write_text(json.dumps({"total": 10, "killed": killed}), encoding="utf-8")
    monkeypatch.setattr(mutation_gate, "STATS", stats)

    assert mutation_gate.main(["--min", "80"]) == code
