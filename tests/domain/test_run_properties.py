"""Property-based tests of the run aggregate: `RunRecord` and its `StepRecord`s.

Example tests pin the transitions someone thought of. These drive random
sequences of every intent method and check two promises the engine relies on:
no sequence reaches a state it cannot reason about (two steps running, a
pending step with an end stamp, a negative duration), and a transition the
status table forbids always raises `InvalidTransition` and leaves the run
exactly as it was — a half-applied change would be saved by the next `save`.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from pulse.domain.control import RUN_BLOCKED, RUN_STOPPED
from pulse.domain.run import (
    InvalidTransition,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
    fan_out_child_id,
)

S = StepStatus
EVERY = frozenset(StepStatus)
SETTLED = frozenset({S.DONE, S.SKIPPED})
ENDED = SETTLED | {S.FAILED, S.BLOCKED}
UNSETTLED_IDLE = EVERY - SETTLED - {S.RUNNING}
GENERIC_FAILURE = 1
EXIT_STATUS = {GENERIC_FAILURE: RunStatus.FAILED, RUN_STOPPED: RunStatus.STOPPED}
EXIT_STATUS[RUN_BLOCKED] = RunStatus.BLOCKED


@dataclass(frozen=True)
class StepAction:
    """One intent method of a step, with the statuses it may start from and where it leads.

    Written from the aggregate's contract, not read from its code, so the test
    is an independent oracle. `leads_to=None` means the status does not change.
    """

    call: Callable[[StepRecord], object]
    allowed_from: frozenset[StepStatus]
    leads_to: StepStatus | None


STEP_ACTIONS = {
    "record_reply": StepAction(
        lambda step: step.record_reply(session_id="session", summary="reply"),
        frozenset({S.RUNNING}),
        None,
    ),
    "deliver": StepAction(lambda step: step.deliver(), frozenset({S.RUNNING}), S.DONE),
    "skip": StepAction(lambda step: step.skip(), frozenset({S.RUNNING}), S.SKIPPED),
    "block": StepAction(lambda step: step.block(), frozenset({S.RUNNING}), S.BLOCKED),
    "fail": StepAction(lambda step: step.fail(), frozenset({S.RUNNING}), S.FAILED),
    "skip_blocked": StepAction(lambda step: step.skip_blocked(), frozenset({S.BLOCKED}), S.SKIPPED),
    "close_after_wait": StepAction(
        lambda step: step.close_after_wait(), frozenset({S.FAILED, S.BLOCKED}), None
    ),
    "reopen_round_as_opener": StepAction(
        lambda step: step.reopen_round(opener=True), EVERY - {S.RUNNING}, S.PENDING
    ),
    "reopen_round": StepAction(
        lambda step: step.reopen_round(opener=False), EVERY - {S.RUNNING}, S.PENDING
    ),
    "close_with_loop_after_a_round": StepAction(
        lambda step: step.close_with_loop(ran_before=True), UNSETTLED_IDLE, S.DONE
    ),
    "close_with_loop_never_ran": StepAction(
        lambda step: step.close_with_loop(ran_before=False), UNSETTLED_IDLE, S.SKIPPED
    ),
    "retire": StepAction(lambda step: step.retire(), UNSETTLED_IDLE, S.SKIPPED),
}

step_picks = st.integers(min_value=0, max_value=63)
step_subsets = st.lists(step_picks, max_size=4)


class RunAggregate(RuleBasedStateMachine):
    """Random walks over the run aggregate, the way the engine and the daemon drive it."""

    run: RunRecord

    @initialize(count=st.integers(min_value=1, max_value=5))
    def start_with_steps(self, count: int) -> None:
        self.run = RunRecord(
            id="run-1",
            workflow_id="demo",
            workspace_root="/workspace",
            steps=[StepRecord(step_id=f"s{index}", position=index) for index in range(count)],
        )
        self.added = 0

    def _pick(self, pick: int) -> StepRecord | None:
        if not self.run.steps:
            return None
        return self.run.steps[pick % len(self.run.steps)]

    def _ids(self, picks: list[int]) -> list[str]:
        """Distinct step ids, as the engine passes a definition range."""
        picked = [step.step_id for pick in picks if (step := self._pick(pick)) is not None]
        return list(dict.fromkeys(picked))

    def _attempt(self, action: Callable[[], object], *, legal: bool) -> None:
        """Run `action`; when illegal it must raise and change nothing at all."""
        if legal:
            action()
            return
        before = copy.deepcopy(self.run)
        with pytest.raises(InvalidTransition):
            action()
        assert self.run == before
        assert self.run.removed_step_ids() == before.removed_step_ids()

    @rule(pick=step_picks, name=st.sampled_from(sorted(STEP_ACTIONS)))
    def act_on_a_step(self, pick: int, name: str) -> None:
        step = self._pick(pick)
        if step is None:
            return
        action = STEP_ACTIONS[name]
        before = step.status
        legal = before in action.allowed_from

        self._attempt(lambda: action.call(step), legal=legal)

        if legal:
            assert step.status == (action.leads_to or before)

    @rule(pick=step_picks)
    def start_a_step(self, pick: int) -> None:
        step = self._pick(pick)
        if step is None:
            return
        others_running = any(
            other.status == S.RUNNING for other in self.run.steps if other is not step
        )
        legal = step.status not in SETTLED and not others_running

        self._attempt(lambda: self.run.start_step(step.step_id), legal=legal)

        if legal:
            assert (step.status, self.run.status, self.run.current_step) == (
                S.RUNNING,
                RunStatus.RUNNING,
                step.step_id,
            )

    @rule()
    def start_a_step_the_run_does_not_have(self) -> None:
        self._attempt(lambda: self.run.start_step("missing"), legal=False)

    @rule(pick=step_picks)
    def release_a_step(self, pick: int) -> None:
        step = self._pick(pick)
        if step is None:
            return
        before = step.status

        changed = step.release()

        interrupted = before in {S.RUNNING, S.FAILED, S.BLOCKED}
        assert changed is interrupted
        assert step.status == (S.PENDING if interrupted else before)

    @rule(pick=step_picks, seconds=st.floats(min_value=-60, max_value=3600))
    def end_a_wait(self, pick: int, seconds: float) -> None:
        step = self._pick(pick)
        if step is None:
            return
        waited = step.waiting_seconds
        status = self.run.status

        self.run.end_wait(step.step_id, seconds)

        assert step.waiting_seconds == waited + max(0.0, seconds)
        resumed = RunStatus.RUNNING if status == RunStatus.AWAITING_INPUT else status
        assert self.run.status == resumed

    @rule()
    def await_input(self) -> None:
        status = self.run.status
        changed = self.run.await_input()
        assert changed is (status == RunStatus.RUNNING)
        assert self.run.status == (RunStatus.AWAITING_INPUT if changed else status)

    @rule()
    def resume_work(self) -> None:
        status = self.run.status
        changed = self.run.resume_work()
        assert changed is (status == RunStatus.AWAITING_INPUT)
        assert self.run.status == (RunStatus.RUNNING if changed else status)

    @rule()
    def complete(self) -> None:
        legal = all(step.status in SETTLED for step in self.run.steps)
        self._attempt(self.run.complete, legal=legal)
        if legal:
            assert self.run.status == RunStatus.COMPLETED

    @rule(exit_code=st.sampled_from([0, GENERIC_FAILURE, RUN_STOPPED, RUN_BLOCKED]))
    def end(self, exit_code: int) -> None:
        self._attempt(lambda: self.run.end(exit_code), legal=exit_code != 0)
        if exit_code != 0:
            assert self.run.status == EXIT_STATUS[exit_code]

    @rule()
    def crash(self) -> None:
        running = [step for step in self.run.steps if step.status == S.RUNNING]

        self.run.crash()

        assert self.run.status == RunStatus.FAILED
        assert all(step.status == S.FAILED for step in running)

    @rule(picks=step_subsets, opener=step_picks)
    def reopen_a_loop(self, picks: list[int], opener: int) -> None:
        step_ids = self._ids(picks)
        opener_step = self._pick(opener)
        opener_id = opener_step.step_id if opener_step is not None else ""
        rounds = opener_step.rounds if opener_step is not None else 0
        legal = all(self.run.step(step_id).status != S.RUNNING for step_id in step_ids)

        self._attempt(lambda: self.run.reopen_loop(step_ids, opener_id=opener_id), legal=legal)

        if legal:
            assert all(self.run.step(step_id).status == S.PENDING for step_id in step_ids)
            if opener_step is not None:
                assert opener_step.rounds == rounds + (opener_id in step_ids)

    @rule(picks=step_subsets, opener=step_picks)
    def close_a_loop(self, picks: list[int], opener: int) -> None:
        step_ids = self._ids(picks)
        opener_step = self._pick(opener)
        opener_id = opener_step.step_id if opener_step is not None else ""
        legal = all(self.run.step(step_id).status != S.RUNNING for step_id in step_ids)

        self._attempt(lambda: self.run.close_loop(step_ids, opener_id=opener_id), legal=legal)

        if legal:
            assert all(self.run.step(step_id).status in SETTLED for step_id in step_ids)

    @rule(picks=step_subsets)
    def retire_steps_the_definition_dropped(self, picks: list[int]) -> None:
        defined = set(self._ids(picks))
        dropped = [
            step
            for step in self.run.steps
            if step.step_id not in defined
            and step.step_id.rpartition(":")[0] not in defined
            and step.status not in SETTLED
        ]
        legal = all(step.status != S.RUNNING for step in dropped)

        self._attempt(lambda: self.run.retire_steps_outside(defined), legal=legal)

        if legal:
            assert all(step.status in SETTLED for step in dropped)

    @rule()
    def add_a_new_step(self) -> None:
        self.added += 1
        record = StepRecord(step_id=f"new{self.added}")

        kept = self.run.add_step(record)

        assert kept is record
        assert self.run.steps[-1] is record

    @rule(pick=step_picks)
    def add_a_step_the_run_already_has(self, pick: int) -> None:
        step = self._pick(pick)
        if step is None:
            return
        before = list(self.run.steps)

        kept = self.run.add_step(StepRecord(step_id=step.step_id))

        assert kept is step
        assert self.run.steps == before

    @rule(pick=step_picks, items=st.lists(st.sampled_from("ABC"), max_size=3, unique=True))
    def fan_out_a_step(self, pick: int, items: list[str]) -> None:
        step = self._pick(pick)
        if step is None:
            return
        children = [
            StepRecord(step_id=fan_out_child_id(step.step_id, item), agent_id=step.agent_id)
            for item in items
        ]

        self.run.expand_step(step.step_id, children)

        ids = [record.step_id for record in self.run.steps]
        assert step.step_id not in ids
        assert all(child.step_id in ids for child in children)

    @invariant()
    def at_most_one_step_runs(self) -> None:
        """One ACP session per step: two running steps would share none."""
        running = [step.step_id for step in self.run.steps if step.status == S.RUNNING]
        assert len(running) <= 1

    @invariant()
    def step_ids_are_unique_and_none_is_both_kept_and_deleted(self) -> None:
        ids = [step.step_id for step in self.run.steps]
        assert len(ids) == len(set(ids))
        assert self.run.removed_step_ids().isdisjoint(ids)

    @invariant()
    def stamps_match_the_status(self) -> None:
        """History renders durations from the stamps; a mismatch shows a wrong time."""
        for step in self.run.steps:
            if step.status == S.RUNNING:
                assert step.started_at is not None
            if step.status in ENDED:
                assert step.ended_at is not None
            if step.status == S.PENDING:
                assert step.ended_at is None

    @invariant()
    def counters_never_go_below_their_floor(self) -> None:
        for step in self.run.steps:
            assert step.rounds >= 1
            assert step.waiting_seconds >= 0
            assert step.carried_seconds >= 0
            assert (step.round_seconds() or 0.0) >= 0
            assert (step.elapsed_seconds() or 0.0) >= 0


RunAggregate.TestCase.settings = settings(max_examples=500, stateful_step_count=50, deadline=None)
test_run_aggregate = RunAggregate.TestCase


@given(st.text())
def test_any_stored_step_status_loads_as_a_known_status(value: str) -> None:
    """A row edited by hand or written by an older version must not break history."""
    parsed = StepStatus.parse(value)

    assert parsed == (StepStatus(value) if value in set(StepStatus) else StepStatus.PENDING)


@given(st.text())
def test_any_stored_run_status_loads_as_a_known_status(value: str) -> None:
    parsed = RunStatus.parse(value)

    assert parsed == (RunStatus(value) if value in set(RunStatus) else RunStatus.PENDING)


@given(st.integers())
def test_every_exit_code_maps_to_an_ended_run_status(exit_code: int) -> None:
    """Stopped and blocked are not failures; every other non-zero code is."""
    expected = {0: RunStatus.COMPLETED, **EXIT_STATUS}.get(exit_code, RunStatus.FAILED)

    assert RunStatus.for_exit_code(exit_code) == expected
