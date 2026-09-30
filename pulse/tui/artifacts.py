"""Artefatos exibidos no cockpit.

Artefato é qualquer arquivo que o agente escreveu — o Pulse descobre pelos
tool-calls do ACP, não por convenção de pasta ou extensão. Por isso não há mais
filtro por `.pulse/specs/**.md`: o caminho chega pronto do runtime e aqui só é
normalizado e lido.
"""

from __future__ import annotations

from pathlib import Path

MAX_ARTIFACT_CHARS = 200_000


def artifact_key(path: str) -> str:
    """Forma canônica de um caminho: barras normais, sem `file://`."""
    text = str(path or "").strip().replace("\\", "/")
    if text.startswith("file://"):
        text = text[7:]
    return text


def artifact_paths_in_text(text: str, known: list[str]) -> list[str]:
    """Artefatos conhecidos que o texto cita.

    Procura só entre os que a run já registrou, em vez de adivinhar caminho por
    regex: sem uma convenção de nome, qualquer padrão inventado casaria com
    trecho de código e apontaria a aba para um arquivo que não é artefato.
    """
    haystack = str(text or "").replace("\\", "/")
    found: list[str] = []
    for candidate in known:
        key = artifact_key(candidate)
        if not key:
            continue
        name = key.rsplit("/", 1)[-1]
        if (key in haystack or name in haystack) and key not in found:
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
