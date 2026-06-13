from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cursor_task.executor.base import ExecutionContext
from cursor_task.executor.completion import resolve_completion
from pulse_specs.discovery import (
    discover_phases,
    phase_branch_name,
    phases_by_number,
    resolve_initial_parent_branch,
    resolve_specs_root,
    validate_branch_namespace,
)
from pulse_specs.git_workflow import branch_exists, current_branch, resolve_repo_root
from pulse_specs.prompt import EXECUTE_SPEC_REFERENCE, build_execute_spec_prompt
from pulse_specs.runner import run_execute_specs_loop
from pulse_specs.skills import resolve_applicable_skills
from pulse_specs.tracker import is_spec_completed, spec_status_path
from pulse_specs.types import ExecuteSpecsOptions


class SpecDiscoveryTests(unittest.TestCase):
    def test_discover_phases_sorted(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        specs_root = resolve_specs_root(backend)
        phases = discover_phases(specs_root)
        self.assertGreaterEqual(len(phases), 14)
        numbers = [phase.number for phase in phases]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(phases[0].slug, "01-agent-provider")

    def test_discover_phases_filter_range(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        specs_root = resolve_specs_root(backend)
        phases = discover_phases(specs_root, from_phase=2, to_phase=3)
        self.assertEqual([phase.number for phase in phases], [2, 3])

    def test_phase_branch_name(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        specs_root = resolve_specs_root(backend)
        phase = discover_phases(specs_root, only=["01-agent-provider"])[0]
        self.assertEqual(
            phase_branch_name("feat/pulse-specs", phase),
            "feat/pulse-specs/01-agent-provider",
        )

    def test_validate_branch_namespace_rejects_conflict(self) -> None:
        with self.assertRaises(ValueError):
            validate_branch_namespace("feat/pulse-backend", "feat/pulse-backend")

    def test_resolve_initial_parent_branch_first_phase(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        specs_root = resolve_specs_root(backend)
        phases = discover_phases(specs_root)
        index = phases_by_number(phases)
        parent = resolve_initial_parent_branch("feat/pulse-backend", "feat/pulse-specs", phases[0], index)
        self.assertEqual(parent, "feat/pulse-backend")

    def test_resolve_initial_parent_branch_mid_chain(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        specs_root = resolve_specs_root(backend)
        phases = discover_phases(specs_root, from_phase=3, to_phase=3)
        index = phases_by_number(discover_phases(specs_root))
        parent = resolve_initial_parent_branch(
            "feat/pulse-backend",
            "feat/pulse-specs",
            phases[0],
            index,
        )
        self.assertEqual(parent, "feat/pulse-specs/02-dynamic-paths")


class SpecPromptTests(unittest.TestCase):
    def test_build_execute_spec_prompt_includes_paths_and_skills(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        repo_root = resolve_repo_root(backend)
        specs_root = resolve_specs_root(backend)
        phase = discover_phases(specs_root, only=["01-agent-provider"])[0]
        shared_docs = sorted((specs_root / "shared").glob("*.md"))
        skills = resolve_applicable_skills(phase, backend)
        status_path = spec_status_path(backend, phase.slug)

        composed = build_execute_spec_prompt(
            repo_root=repo_root,
            artifacts_path=backend,
            product_path=phase.product_path,
            technical_path=phase.technical_path,
            shared_docs=shared_docs,
            skills=skills,
            phase_slug=phase.slug,
            phase_branch="feat/pulse-specs/01-agent-provider",
            parent_branch="feat/pulse-backend",
            pr_base_branch="feat/pulse-backend",
            status_path=status_path,
        )

        self.assertIn(EXECUTE_SPEC_REFERENCE, composed)
        self.assertIn("01-agent-provider", composed)
        self.assertIn("feat/pulse-specs/01-agent-provider", composed)
        self.assertIn("create-pr/SKILL.md", composed)
        self.assertIn("python-expert", composed)


class SpecTrackerTests(unittest.TestCase):
    def test_is_spec_completed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "_status.md"
            self.assertFalse(is_spec_completed(status_path))
            status_path.write_text("status: completed\n", encoding="utf-8")
            self.assertTrue(is_spec_completed(status_path))


class SpecCompletionTests(unittest.TestCase):
    def test_resolve_spec_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "_status.md"
            from cursor_task.artifact_writer import ArtifactWriter
            from cursor_task.question_handler import QuestionHandler
            from cursor_task.stream_renderer import StreamRenderer

            context = ExecutionContext(
                prompt="",
                renderer=StreamRenderer(),
                question_handler=QuestionHandler(renderer=StreamRenderer()),
                artifact_writer=ArtifactWriter(artifacts_path=Path(tmp), artifact_kind="tasks"),
                execution_mode="spec",
                execute_spec_status_file=status_path,
            )
            ready, next_prompt = resolve_completion(context)
            self.assertFalse(ready)
            self.assertIsNotNone(next_prompt)

            status_path.write_text("status: completed\n", encoding="utf-8")
            ready, next_prompt = resolve_completion(context)
            self.assertTrue(ready)
            self.assertIsNone(next_prompt)


class GitWorkflowTests(unittest.TestCase):
    def test_resolve_repo_root_from_backend(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        repo_root = resolve_repo_root(backend)
        self.assertTrue((repo_root / "backend").is_dir())

    def test_current_branch_and_exists(self) -> None:
        backend = Path(__file__).resolve().parents[1]
        repo_root = resolve_repo_root(backend)
        branch = current_branch(repo_root)
        self.assertTrue(branch)
        self.assertTrue(branch_exists(repo_root, branch))


class ExecuteSpecsOptionsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        options = ExecuteSpecsOptions()
        self.assertEqual(options.parent_branch, "feat/pulse-backend")
        self.assertEqual(options.branch_prefix, "feat/pulse-specs")
        self.assertEqual(options.reference, "execute-spec")
        self.assertFalse(options.dry_run)


class SpecChainTests(unittest.TestCase):
    def test_dry_run_shows_sequential_parents(self) -> None:
        from io import StringIO
        from contextlib import redirect_stdout

        buffer = StringIO()
        with redirect_stdout(buffer):
            run_execute_specs_loop(
                ExecuteSpecsOptions(
                    from_phase=1,
                    to_phase=3,
                    dry_run=True,
                )
            )
        output = buffer.getvalue()
        self.assertIn("[dry-run] 01-agent-provider | branch: feat/pulse-specs/01-agent-provider | base: feat/pulse-backend", output)
        self.assertIn(
            "[dry-run] 02-dynamic-paths | branch: feat/pulse-specs/02-dynamic-paths | base: feat/pulse-specs/01-agent-provider",
            output,
        )
        self.assertIn(
            "[dry-run] 03-db-projects | branch: feat/pulse-specs/03-db-projects | base: feat/pulse-specs/02-dynamic-paths",
            output,
        )
