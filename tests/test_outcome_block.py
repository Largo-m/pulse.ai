"""The `pulse:outcome` block: what the engine accepts as "delivered"."""

from __future__ import annotations

from pulse.orchestrator.outcome import LoopSignal, OutcomeStatus, parse_outcome


def _block(body: str) -> str:
    return f"texto do agente\n\n```pulse:outcome\n{body}\n```\n"


def test_done_is_the_only_way_to_say_delivered():
    assert parse_outcome(_block("status: done")).delivered


def test_text_without_the_block_is_not_a_delivery():
    """This is exactly what used to become `done`: ending the turn with nice words."""
    outcome = parse_outcome("terminei o que dava, mas falta a credencial do banco")
    assert outcome.status == OutcomeStatus.MISSING
    assert not outcome.delivered


def test_a_block_carries_the_reason_the_person_is_going_to_read():
    outcome = parse_outcome(_block("status: blocked\nreason: falta DATABASE_URL"))
    assert outcome.status == OutcomeStatus.BLOCKED
    assert outcome.reason == "falta DATABASE_URL"
    assert not outcome.needs_user


def test_needs_marks_what_the_agent_cannot_solve_alone():
    outcome = parse_outcome(_block("status: blocked\nreason: sem acesso\nneeds: user"))
    assert outcome.needs_user

    with_comment = parse_outcome(
        _block("status: blocked\nreason: x\nneeds: permission   # só quando depender")
    )
    assert with_comment.needs_user


def test_the_last_block_wins():
    """A step that went through a continuation has two blocks; the bottom one wins."""
    text = _block("status: blocked\nreason: falta config") + _block("status: done")
    assert parse_outcome(text).status == OutcomeStatus.DONE


def test_a_status_nobody_recognises_counts_as_blocked():
    """The engine cannot confirm delivery, and erring on the safe side costs one extra on-screen question."""
    outcome = parse_outcome(_block("status: parcialmente feito"))
    assert outcome.status == OutcomeStatus.BLOCKED
    assert not outcome.delivered


def test_the_agent_may_answer_in_the_language_of_the_prompt():
    outcome = parse_outcome(_block("status: bloqueado\nmotivo: falta o token\nprecisa: usuário"))
    assert outcome.status == OutcomeStatus.BLOCKED
    assert outcome.reason == "falta o token"
    assert outcome.needs_user


def test_a_reason_the_size_of_a_stack_trace_is_cut():
    outcome = parse_outcome(_block(f"status: blocked\nreason: {'x' * 5000}"))
    assert len(outcome.reason) <= 400


def test_punctuation_or_markdown_around_done_still_counts_as_delivered():
    for status in ("done.", "**done**", "`done`", "done — entreguei"):
        assert parse_outcome(_block(f"status: {status}")).status == OutcomeStatus.DONE, status


def test_the_reason_keeps_issue_and_pr_references():
    outcome = parse_outcome(_block("status: blocked\nreason: sem acesso ao repo (PR #29)"))
    assert outcome.reason == "sem acesso ao repo (PR #29)"


def test_next_is_parsed_into_a_loop_signal_and_unknown_words_are_dropped():
    assert parse_outcome(_block("status: done\nnext: repetir")).next is LoopSignal.REPEAT
    assert parse_outcome(_block("status: done\npróximo: **encerrar**")).next is LoopSignal.CLOSE
    assert parse_outcome(_block("status: done\nnext: talvez")).next is None
    assert parse_outcome(_block("status: done")).next is None


def test_only_a_delivery_can_steer_the_loop():
    """A blocked step asking for another round would loop on a failure."""
    repeat = parse_outcome(_block("status: done\nnext: repeat"))
    assert repeat.repeats and not repeat.closes

    close = parse_outcome(_block("status: done\nnext: close"))
    assert close.closes and not close.repeats

    blocked = parse_outcome(_block("status: blocked\nnext: repeat"))
    assert not blocked.repeats and not blocked.closes
