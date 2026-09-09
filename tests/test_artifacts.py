from __future__ import annotations

from pulse.tui.artifacts import (
    MAX_ARTIFACT_CHARS,
    artifact_key,
    extract_spec_artifacts_from_text,
    is_spec_artifact,
    read_artifact_markdown,
)


def test_is_spec_artifact_accepts_pulse_specs_markdown():
    assert is_spec_artifact(".pulse/specs/project/PROJECT.md")
    assert is_spec_artifact("/repo/.pulse/specs/features/demo/spec.md")
    assert is_spec_artifact("file:///tmp/.pulse/specs/quick/001-x/TASK.md")


def test_is_spec_artifact_rejects_skills_and_non_markdown():
    assert not is_spec_artifact(".pulse/skills/tlc-spec-driven/SKILL.md")
    assert not is_spec_artifact(".pulse/specs/skills/tlc-spec-driven/prompts/specify.md")
    assert not is_spec_artifact(".pulse/specs/project/STATE.yaml")
    assert not is_spec_artifact("spec.md")
    assert not is_spec_artifact("pulse/cli.py")


def test_artifact_key_normalizes_absolute_paths():
    assert artifact_key("/repo/.pulse/specs/project/STATE.md") == ".pulse/specs/project/STATE.md"
    assert artifact_key(".pulse/specs/project/STATE.md") == ".pulse/specs/project/STATE.md"


def test_extract_spec_artifacts_from_prompt_text():
    text = "1. Aprovar Specify (`.pulse/specs/features/demo/spec.md`) e avançar?"
    assert extract_spec_artifacts_from_text(text) == [
        ".pulse/specs/features/demo/spec.md"
    ]
    mixed = "veja .pulse/specs/skills/foo.md e .pulse/specs/codebase/STACK.md"
    assert extract_spec_artifacts_from_text(mixed) == [".pulse/specs/codebase/STACK.md"]


def test_read_artifact_markdown_truncates_and_missing(tmp_path):
    missing_text, missing_mtime, exists = read_artifact_markdown(
        ".pulse/specs/project/PROJECT.md",
        cwd=str(tmp_path),
    )
    assert exists is False
    assert missing_text == ""
    assert missing_mtime == 0.0

    target = tmp_path / ".pulse/specs/project/PROJECT.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Visão\n\nApp demo.\n", encoding="utf-8")
    text, mtime, exists = read_artifact_markdown(
        ".pulse/specs/project/PROJECT.md",
        cwd=str(tmp_path),
    )
    assert exists is True
    assert "# Visão" in text
    assert mtime > 0

    huge = tmp_path / ".pulse/specs/codebase/STACK.md"
    huge.parent.mkdir(parents=True, exist_ok=True)
    huge.write_text("x" * (MAX_ARTIFACT_CHARS + 50), encoding="utf-8")
    truncated, _, exists = read_artifact_markdown(
        ".pulse/specs/codebase/STACK.md",
        cwd=str(tmp_path),
    )
    assert exists is True
    assert truncated.endswith("[… artefato truncado …]")
    assert len(truncated) < MAX_ARTIFACT_CHARS + 80
