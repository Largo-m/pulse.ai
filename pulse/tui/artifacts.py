from __future__ import annotations

import re
from pathlib import Path

MAX_ARTIFACT_CHARS = 200_000
_SPECS_TOKEN = ".pulse/specs/"
_TEXT_PATH_RE = re.compile(r"\.pulse/specs/[A-Za-z0-9_./-]+\.md")


def artifact_key(path: str) -> str:
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith("file://"):
        text = text[7:]
    marker = text.find(_SPECS_TOKEN)
    if marker >= 0:
        return text[marker:]
    return text


def is_spec_artifact(path: str) -> bool:
    key = artifact_key(path)
    if not key.lower().endswith(".md"):
        return False
    if ".pulse/skills/" in key or ".pulse/specs/skills/" in key:
        return False
    return _SPECS_TOKEN in key


def extract_spec_artifacts_from_text(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _TEXT_PATH_RE.finditer(text or ""):
        key = artifact_key(match.group(0))
        if key in seen or not is_spec_artifact(key):
            continue
        seen.add(key)
        found.append(key)
    return found


def resolve_artifact_path(path: str, cwd: str | None = None) -> Path:
    key = artifact_key(path)
    raw = Path(str(path or "").strip())
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    if cwd:
        root = Path(cwd)
        candidates.append(root / key)
        stripped = str(path or "").strip()
        if stripped and stripped != key:
            candidates.append(root / stripped)
    else:
        candidates.append(Path(key))
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return candidates[0] if candidates else Path(key)


def artifact_has_content(path: str, cwd: str | None = None) -> bool:
    """Arquivo existe e não está vazio — há algo de fato para exibir."""
    target = resolve_artifact_path(path, cwd)
    try:
        return target.is_file() and target.stat().st_size > 0
    except OSError:
        return False


def read_artifact_markdown(path: str, cwd: str | None = None) -> tuple[str, float, bool]:
    target = resolve_artifact_path(path, cwd)
    try:
        if not target.is_file():
            return "", 0.0, False
        mtime = target.stat().st_mtime
        text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", 0.0, False
    if len(text) > MAX_ARTIFACT_CHARS:
        text = text[:MAX_ARTIFACT_CHARS].rstrip() + "\n\n[… artefato truncado …]"
    return text, mtime, True
