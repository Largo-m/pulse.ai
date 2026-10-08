"""The docs describe the code that exists: no dead links, no module that was removed.

`ARCHITECTURE.md` and `AGENTS.md` are what agents read before changing the
repo; a stale path there sends them to edit code that is gone.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / "pulse"
# Playbooks are prompt data seeded into SQLite, not repo docs: their links are
# relative to the skill they came from and are never followed from the repo.
FACTORY = "pulse/store/factory/"
FENCED_BLOCK = re.compile(r"^(```|~~~).*?^\1", re.DOTALL | re.MULTILINE)
INLINE_CODE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[[^\]\n]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
URL_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)
CODE_PATH = re.compile(r"^[\w./*-]+$")


def _tracked_markdown() -> list[Path]:
    """What the repo ships, not whatever else sits in a local checkout."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],  # noqa: S607 - git is resolved from PATH like in CI
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [ROOT / name for name in listing.split("\0") if name and not name.startswith(FACTORY)]


def broken_links(document: Path, text: str) -> list[str]:
    prose = INLINE_CODE.sub("", FENCED_BLOCK.sub("", text))
    broken = []
    for match in LINK.finditer(prose):
        target = match.group(1)
        if URL_SCHEME.match(target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        resolved = ROOT / path.lstrip("/") if path.startswith("/") else document.parent / path
        if not resolved.exists():
            broken.append(target)
    return broken


def _dotted_module_exists(citation: str) -> bool:
    """`pulse.x.y` or `pulse.x.y.attribute`."""
    parts = citation.split(".")[1:]
    return _is_module(PACKAGE.joinpath(*parts)) or _is_module(PACKAGE.joinpath(*parts[:-1]))


def _path_module_exists(relative: str) -> bool:
    """`x/`, `x/*.py`, `x/y.py` or `x/y.attribute`, relative to the package."""
    if any(char in relative for char in "*?["):
        return any(PACKAGE.glob(relative))
    path = PACKAGE / relative.rstrip("/")
    return path.exists() or _is_module(path.with_name(path.name.split(".", 1)[0]))


def _is_module(path: Path) -> bool:
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def stale_module_citations(text: str) -> list[str]:
    """Code spans naming a Pulse module that doesn't exist.

    A span counts as a citation when it starts with `pulse/`, `pulse.` or a
    first-level subpackage (`store/db.py`); prose examples like `src/main.rs`
    name no Pulse module and are left alone.
    """
    subpackages = {path.name for path in PACKAGE.iterdir() if (path / "__init__.py").is_file()}
    stale = []
    for span in INLINE_CODE.findall(text):
        citation = span.split("(", 1)[0]
        if not CODE_PATH.match(citation):
            continue
        if citation.startswith("pulse."):
            exists = _dotted_module_exists(citation)
        elif citation.startswith("pulse/"):
            exists = _path_module_exists(citation.removeprefix("pulse/"))
        elif "/" in citation and citation.split("/", 1)[0] in subpackages:
            exists = _path_module_exists(citation)
        else:
            continue
        if not exists:
            stale.append(span)
    return stale


def test_markdown_links_resolve() -> None:
    broken = {
        document.relative_to(ROOT).as_posix(): links
        for document in _tracked_markdown()
        if (links := broken_links(document, document.read_text(encoding="utf-8")))
    }

    assert broken == {}


def test_architecture_doc_modules_exist() -> None:
    text = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")

    assert stale_module_citations(text) == []


def test_the_link_check_tells_a_dead_link_from_a_live_one() -> None:
    """Guards the guard: a checker that resolves nothing would pass forever."""
    document = ROOT / "AGENTS.md"
    text = (
        "[ok](ARCHITECTURE.md#layers) [web](https://example.com) [anchor](#top)\n"
        "[dead](docs/gone.md) `[code](ignored.md)`\n"
        "```\n[fenced](also-ignored.md)\n```\n"
    )

    assert broken_links(document, text) == ["docs/gone.md"]


def test_the_module_check_tells_a_removed_module_from_a_present_one() -> None:
    text = (
        "`pulse/orchestrator/engine.py` `pulse.store.workflow_defs.save_workflow()` "
        "`history/tool_detail.build_tool_labels` `pulse/tui/screens/history*.py` `acp/` "
        "`src/main.rs` `engine/` `pulse init` "
        "`pulse/daemon/protocol.py` `pulse.orchestrator.gone.run()` `store/gone.py` `domain/old/`"
    )

    assert stale_module_citations(text) == [
        "pulse/daemon/protocol.py",
        "pulse.orchestrator.gone.run()",
        "store/gone.py",
        "domain/old/",
    ]
