"""Regras de fase que vivem no texto do prompt.

O comportamento aqui é o que o agente lê, não o que o Python executa: os testes
travam as três regras que o pipeline não consegue impor sozinho — PRD
pergunta até zerar, PRD não fala técnico, e a implementação só escreve teste
de unidade.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pulse.agents.build import build_all, render_agent
from pulse.agents.catalog import AGENT_BY_ID
from pulse.plan.new_issue_prompt import (
    build_techspec_prompt,
    build_execute_task_prompt,
    build_phase_continuation_prompt,
    build_prd_prompt,
    build_tasks_prompt,
)
from pulse.plan.workflow_state import WorkflowState
from pulse.skills.loader import resolve_bundled_skill

SKILL = resolve_bundled_skill("pulse-spec-driven")
REFERENCES = SKILL / "references"


def _state() -> WorkflowState:
    return WorkflowState.create_new(feature_slug="login-email", user_prompt="Login com e-mail")


def _prd_prompt(tmp_path: Path) -> str:
    return build_prd_prompt(
        workspace=tmp_path,
        user_prompt="Login com e-mail",
        skill_dir=SKILL,
        state=_state(),
    )


def test_prd_loops_until_no_open_question(tmp_path: Path):
    prompt = _prd_prompt(tmp_path)
    assert "Clarify — keep asking until nothing is open (mandatory)" in prompt
    assert "A question block and an approval block never appear in the same reply" in prompt
    assert "There is no cap on rounds" in prompt


def test_prd_forbids_assumed_ledger_rows(tmp_path: Path):
    prompt = _prd_prompt(tmp_path)
    assert "Writing `assumed` in the Ambiguity Ledger" in prompt
    assert "if you were about to assume it, ask it" in prompt


def test_prd_approval_block_is_conditional(tmp_path: Path):
    prompt = _prd_prompt(tmp_path)
    # Aprovação deixa de ser o fecho padrão: só vale com o ledger limpo.
    assert "Use this block **only when nothing is left open" in prompt
    assert "with the clarify question block" in prompt


def test_prd_bans_technical_vocabulary(tmp_path: Path):
    prompt = _prd_prompt(tmp_path)
    assert "### Product language only" in prompt
    for term in ("retry", "backoff", "TTL", "rate limit", "webhook"):
        assert term in prompt, f"termo proibido `{term}` não listado no prompt"
    assert "The implicit-requirement sweep" in prompt
    assert "does not** run here" in prompt


def test_technical_terms_are_listed_verbatim(tmp_path: Path):
    """A lista de termos banidos mora no template, não no Python."""
    from pulse.prompts.templates import load_shared

    clarify = load_shared("clarify").text
    for term in ("idempotency", "race condition", "transaction", "middleware", "deploy"):
        assert term in clarify
    assert clarify in _prd_prompt(tmp_path)


def test_prd_continuation_asks_again_when_doubt_remains(tmp_path: Path):
    prompt = build_phase_continuation_prompt(
        workspace=tmp_path,
        user_prompt="Login com e-mail",
        skill_dir=SKILL,
        state=_state(),
        phase="prd",
        phase_summary="rascunho anterior",
        questionnaire_answers="→ A) Mostrar o carrinho salvo",
        outcome="continue",
        prompt_builder=build_prd_prompt,
    )
    assert "is any gray area, doubt or `open` row still left" in prompt
    assert "No approval block" in prompt
    assert "writing `assumed` in the ledger" in prompt


def test_techspec_owns_the_implicit_requirement_sweep(tmp_path: Path):
    prompt = build_techspec_prompt(
        workspace=tmp_path,
        user_prompt="Login com e-mail",
        skill_dir=SKILL,
        state=_state(),
    )
    assert "implicit-requirement sweep** belongs to this phase" in prompt
    assert "idempotency/retry" in prompt
    assert "`assumed` does not" in prompt
    assert "Technical vocabulary is welcome" in prompt


def test_execute_writes_unit_tests_only(tmp_path: Path):
    prompt = build_execute_task_prompt(
        workspace=tmp_path,
        user_prompt="Login com e-mail",
        skill_dir=SKILL,
        state=_state(),
        task_id="T1",
        task_title="Criar formulário de login",
        tasks_skipped=False,
    )
    assert "Unit tests only in this phase" in prompt
    assert "Do not write integration or end-to-end tests" in prompt
    assert "Deferred test coverage" in prompt


def test_tasks_phase_defers_integration_and_e2e(tmp_path: Path):
    prompt = build_tasks_prompt(
        workspace=tmp_path,
        user_prompt="Login com e-mail",
        skill_dir=SKILL,
        state=_state(),
    )
    assert "No task carries `Tests: integration` or `Tests: e2e`" in prompt
    assert "Deferred test coverage" in prompt


def test_references_drop_assumed_as_a_closing_status():
    ambiguity = (REFERENCES / "ambiguity.md").read_text(encoding="utf-8")
    assert "There is no `assumed`" in ambiguity
    assert "| `assumed` |" not in ambiguity
    prd = (REFERENCES / "prd.md").read_text(encoding="utf-8")
    assert "no `assumed` rows" in prd


def test_implicit_sweep_moved_from_prd_to_techspec():
    prd = (REFERENCES / "prd.md").read_text(encoding="utf-8")
    techspec = (REFERENCES / "techspec.md").read_text(encoding="utf-8")
    assert "does **not** run here. Techspec owns it" in prd
    assert "Implicit-requirement sweep (Techspec owns this)" in techspec
    assert "| Idempotency / retry / dedup |" in techspec
    assert "| Idempotency / retry / dedup |" not in prd


def test_implement_reference_allows_unit_tests_only():
    implement = (REFERENCES / "implement.md").read_text(encoding="utf-8")
    assert "**Unit tests only.**" in implement
    assert "There is no Full gate in Execute" in implement
    assert "| E2E or integration tests         | Full" not in implement


def test_tasks_reference_has_deferred_coverage_section():
    tasks = (REFERENCES / "tasks.md").read_text(encoding="utf-8")
    assert "## Deferred test coverage" in tasks
    assert "`Tests: integration` and `Tests: e2e` are never valid on a task" in tasks


def _run_validate_prd(spec_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "validate_prd.py"), str(spec_dir)],
        capture_output=True,
        text=True,
    )


def _write_spec(tmp_path: Path, ledger_row: str) -> Path:
    spec_dir = tmp_path / "feature"
    spec_dir.mkdir()
    (spec_dir / "PRD.md").write_text(
        "\n".join(
            [
                "# Login Specification",
                "",
                "## Motivating Problem",
                "",
                "Quem já tem conta não consegue voltar. **Slice 1 outcome:** a pessoa entra com",
                "e-mail e senha e vê a própria lista de pedidos.",
                "",
                "## Problem Statement",
                "",
                "Pessoas não conseguem entrar.",
                "",
                "## Out of Scope",
                "",
                "| Feature | Reason |",
                "| ------- | ------ |",
                "| SSO | outra entrega |",
                "",
                "## Ambiguity Ledger",
                "",
                "| ID | Topic | Status | Resolution | Rationale |",
                "| -- | ----- | ------ | ---------- | --------- |",
                ledger_row,
                "",
                "## User Stories",
                "",
                "### P1: Entrar com e-mail",
                "",
                "**Acceptance Criteria**:",
                "",
                "1. WHEN a pessoa envia e-mail e senha corretos THEN the system SHALL abrir a sessão",
                "",
                "## Requirement Traceability",
                "",
                "| Requirement ID | Story | Phase | Status |",
                "| -------------- | ----- | ----- | ------ |",
                "| LOGIN-01 | P1 | Techspec | Pending |",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return spec_dir


def test_validate_prd_rejects_assumed_rows(tmp_path: Path):
    spec_dir = _write_spec(tmp_path, "| AL-01 | Sessão expira | assumed | 30 min | padrão do mercado |")
    result = _run_validate_prd(spec_dir)
    assert result.returncode != 0
    assert "assumed row(s)" in result.stdout + result.stderr


def test_validate_prd_accepts_decided_rows(tmp_path: Path):
    spec_dir = _write_spec(
        tmp_path,
        "| AL-01 | Sessão expira | decided | 30 min | time de produto, 2026-09-28 |",
    )
    result = _run_validate_prd(spec_dir)
    assert result.returncode == 0, result.stdout + result.stderr


def test_bundled_agents_are_in_sync_with_references():
    """Editar um AGENT.md à mão faz o bundle divergir da reference."""
    stale = build_all(write=False)
    assert stale == [], (
        "AGENT.md fora de sincronia com as references: "
        f"{', '.join(stale)}. Rode `python -m pulse.agents.build`."
    )


def test_agent_bundle_carries_the_new_prd_rules():
    rendered = render_agent(AGENT_BY_ID["prd"])
    assert "There is no `assumed`" not in rendered  # ambiguity.md não é embutido
    assert "No open question survives this phase" in rendered
    assert "## Product language only" in rendered
    assert "## Clarify loop (mandatory)" in rendered
