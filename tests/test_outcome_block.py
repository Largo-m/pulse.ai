"""O bloco `pulse:outcome`: o que o motor aceita como "entreguei"."""

from __future__ import annotations

from pulse.orchestrator.outcome import BLOCKED, DONE, MISSING, parse_outcome


def _block(body: str) -> str:
    return f"texto do agente\n\n```pulse:outcome\n{body}\n```\n"


def test_done_is_the_only_way_to_say_delivered():
    assert parse_outcome(_block("status: done")).delivered


def test_text_without_the_block_is_not_a_delivery():
    """Era exatamente isto que virava `done`: encerrar o turno falando bonito."""
    outcome = parse_outcome("terminei o que dava, mas falta a credencial do banco")
    assert outcome.status == MISSING
    assert not outcome.delivered


def test_a_block_carries_the_reason_the_person_is_going_to_read():
    outcome = parse_outcome(_block("status: blocked\nreason: falta DATABASE_URL"))
    assert outcome.status == BLOCKED
    assert outcome.reason == "falta DATABASE_URL"
    assert not outcome.needs_user


def test_needs_marks_what_the_agent_cannot_solve_alone():
    outcome = parse_outcome(_block("status: blocked\nreason: sem acesso\nneeds: user"))
    assert outcome.needs_user

    # O exemplo do protocolo vem com comentário na linha; o valor é o token.
    with_comment = parse_outcome(
        _block("status: blocked\nreason: x\nneeds: permission   # só quando depender")
    )
    assert with_comment.needs_user


def test_the_last_block_wins():
    """Um step que passou por continuação tem dois blocos; vale o de baixo."""
    text = _block("status: blocked\nreason: falta config") + _block("status: done")
    assert parse_outcome(text).status == DONE


def test_a_status_nobody_recognises_counts_as_blocked():
    """O motor não tem como afirmar a entrega, e errar para o lado seguro custa
    uma pergunta a mais na tela."""
    outcome = parse_outcome(_block("status: parcialmente feito"))
    assert outcome.status == BLOCKED
    assert not outcome.delivered


def test_the_agent_may_answer_in_the_language_of_the_prompt():
    outcome = parse_outcome(_block("status: bloqueado\nmotivo: falta o token\nprecisa: usuário"))
    assert outcome.status == BLOCKED
    assert outcome.reason == "falta o token"
    assert outcome.needs_user


def test_a_reason_the_size_of_a_stack_trace_is_cut():
    outcome = parse_outcome(_block(f"status: blocked\nreason: {'x' * 5000}"))
    assert len(outcome.reason) <= 400
