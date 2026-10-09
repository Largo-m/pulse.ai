from __future__ import annotations

from pulse.tui.artifacts import (
    MAX_ARTIFACT_CHARS,
    artifact_key,
    artifact_paths_in_text,
    read_artifact_markdown,
)


def test_artifact_key_normalizes_scheme_and_separators():
    assert artifact_key("file:///repo/docs/PLANO.md") == "/repo/docs/PLANO.md"
    assert artifact_key(r"docs\notas.txt") == "docs/notas.txt"
    assert artifact_key("  src/app.py  ") == "src/app.py"


def test_artifact_paths_in_text_only_matches_known_artifacts():
    """With no folder convention, guessing paths by regex would point at code."""
    known = ["docs/PLANO.md", "src/app.py"]
    text = "Aprovar `docs/PLANO.md` e seguir? (não mexa em outro/arquivo.md)"
    assert artifact_paths_in_text(text, known) == ["docs/PLANO.md"]


def test_artifact_paths_in_text_matches_by_file_name():
    known = ["/repo/docs/PLANO.md"]
    assert artifact_paths_in_text("revisei o PLANO.md", known) == ["/repo/docs/PLANO.md"]
    assert artifact_paths_in_text("nada aqui", known) == []


def test_read_artifact_markdown_truncates_and_missing(tmp_path):
    missing_text, missing_mtime, exists = read_artifact_markdown(
        "docs/PROJECT.md",
        cwd=str(tmp_path),
    )
    assert exists is False
    assert missing_text == ""
    assert missing_mtime == 0.0

    target = tmp_path / "docs/PROJECT.md"
    target.parent.mkdir(parents=True)
    target.write_text("# Visão\n\nApp demo.\n", encoding="utf-8")
    text, mtime, exists = read_artifact_markdown("docs/PROJECT.md", cwd=str(tmp_path))
    assert exists is True
    assert "# Visão" in text
    assert mtime > 0

    huge = tmp_path / "notas/STACK.md"
    huge.parent.mkdir(parents=True, exist_ok=True)
    huge.write_text("x" * (MAX_ARTIFACT_CHARS + 50), encoding="utf-8")
    truncated, _, exists = read_artifact_markdown("notas/STACK.md", cwd=str(tmp_path))
    assert exists is True
    assert truncated.endswith("[… artefato truncado …]")
    assert len(truncated) < MAX_ARTIFACT_CHARS + 80


def test_read_artifact_is_not_limited_to_markdown():
    """An artifact is whatever the agent wrote, not just `.md` in a specs folder."""
    assert artifact_key("src/main.rs") == "src/main.rs"
