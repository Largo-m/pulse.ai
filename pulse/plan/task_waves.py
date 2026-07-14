from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


MAX_WAVE_SIZE = 5
_GATE_LINE_RE = re.compile(
    r"Gate check passes:\s*`([^`]+)`",
    re.IGNORECASE,
)
_VERIFY_CMD_RE = re.compile(
    r"^\s*(flutter\s+(?:test|analyze|pub\s+get)|dart\s+analyze|npm\s+test|pytest|cargo\s+test|go\s+test)\b.*$",
    re.IGNORECASE | re.MULTILINE,
)
_CMD_PREFIX_RE = re.compile(
    r"^(flutter\s+(?:test|analyze|pub\s+get)|dart\s+analyze|npm\s+test|pytest|cargo\s+test|go\s+test)\b",
    re.IGNORECASE,
)
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_TASK_HEADER_RE = re.compile(
    r"^###\s+(T\d+):\s*(.+)$",
    re.MULTILINE,
)
_DEPENDS_RE = re.compile(
    r"^\*\*Depends on\*\*:\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)
_WHERE_RE = re.compile(
    r"^\*\*Where\*\*:\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)
_DONE_WHEN_BLOCK_RE = re.compile(
    r"\*\*Done when\*\*:\s*\n((?:.*\n)*?)(?=\n\*\*|\n### |\Z)",
    re.IGNORECASE,
)
_VERIFY_BLOCK_RE = re.compile(
    r"\*\*Verify\*\*:\s*\n((?:.*\n)*?)(?=\n\*\*|\n### |\Z)",
    re.IGNORECASE,
)
_TASK_ID_TOKEN_RE = re.compile(r"\bT\d+\b")


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    depends_on: tuple[str, ...] = ()
    parallel: bool = False
    where: str = ""
    gate_commands: tuple[str, ...] = ()
    file_count_hint: int = 0


@dataclass(frozen=True)
class Wave:
    wave_id: int
    tasks: tuple[TaskSpec, ...]
    parallel: bool = False

    @property
    def task_ids(self) -> list[str]:
        return [task.task_id for task in self.tasks]

    @property
    def label(self) -> str:
        ids = ", ".join(self.task_ids)
        mode = "paralela" if self.parallel else "sequencial"
        return f"Wave {self.wave_id} ({mode}): {ids}"


@dataclass(frozen=True)
class GateResult:
    ok: bool
    command: str
    exit_code: int
    output: str = ""


def parse_task_specs(content: str) -> list[TaskSpec]:
    headers = list(_TASK_HEADER_RE.finditer(content))
    specs: list[TaskSpec] = []
    for index, match in enumerate(headers):
        start = match.start()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(content)
        body = content[start:end]
        task_id = match.group(1)
        raw_title = match.group(2).strip()
        parallel = bool(re.search(r"\[P\]", raw_title))
        title = re.sub(r"\s*\[P\]\s*$", "", raw_title).strip()
        depends_on = _parse_depends_on(body)
        where = _parse_where(body)
        gate_commands = _parse_gate_commands(body)
        file_count_hint = _count_file_hints(where)
        specs.append(
            TaskSpec(
                task_id=task_id,
                title=title,
                depends_on=depends_on,
                parallel=parallel,
                where=where,
                gate_commands=gate_commands,
                file_count_hint=file_count_hint,
            )
        )
    return specs


def build_waves(
    specs: list[TaskSpec],
    *,
    done_ids: set[str] | None = None,
    max_wave_size: int = MAX_WAVE_SIZE,
) -> list[Wave]:
    if max_wave_size < 1:
        raise ValueError("max_wave_size must be >= 1")

    completed = set(done_ids or ())
    remaining = [spec for spec in specs if spec.task_id not in completed]
    waves: list[Wave] = []
    wave_id = 1

    while remaining:
        wave_tasks = _pick_next_wave(remaining, completed, max_wave_size)
        if not wave_tasks:
            wave_tasks = [remaining[0]]

        parallel = len(wave_tasks) > 1 and all(task.parallel for task in wave_tasks)
        waves.append(Wave(wave_id=wave_id, tasks=tuple(wave_tasks), parallel=parallel))
        wave_id += 1

        for task in wave_tasks:
            completed.add(task.task_id)
            remaining = [item for item in remaining if item.task_id != task.task_id]

    return waves


def collect_wave_gate_commands(wave: Wave) -> list[str]:
    seen: set[str] = set()
    commands: list[str] = []
    for task in wave.tasks:
        for command in task.gate_commands:
            normalized = command.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            commands.append(normalized)
    return commands


def run_gate_command(
    *,
    workspace: Path,
    command: str,
    timeout_seconds: int = 600,
) -> GateResult:
    try:
        completed = subprocess.run(
            command,
            shell=True,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return GateResult(ok=False, command=command, exit_code=1, output=str(error))

    output = "\n".join(
        part for part in (completed.stdout or "", completed.stderr or "") if part
    ).strip()
    return GateResult(
        ok=completed.returncode == 0,
        command=command,
        exit_code=completed.returncode,
        output=output,
    )


def run_wave_gates(
    *,
    workspace: Path,
    wave: Wave,
    timeout_seconds: int = 600,
) -> list[GateResult]:
    results: list[GateResult] = []
    for command in collect_wave_gate_commands(wave):
        results.append(
            run_gate_command(
                workspace=workspace,
                command=command,
                timeout_seconds=timeout_seconds,
            )
        )
    return results


def _pick_next_wave(
    remaining: list[TaskSpec],
    completed: set[str],
    max_wave_size: int,
) -> list[TaskSpec]:
    ready = [task for task in remaining if _deps_satisfied(task, completed)]
    if not ready:
        return []

    first = ready[0]
    wave: list[TaskSpec] = [first]
    wave_ids = {first.task_id}
    want_parallel = first.parallel

    for candidate in ready[1:]:
        if len(wave) >= max_wave_size:
            break
        if candidate.parallel != want_parallel:
            break
        if not _deps_satisfied(candidate, completed | wave_ids):
            continue
        if want_parallel and not candidate.parallel:
            break
        if not want_parallel and candidate.parallel:
            break
        wave.append(candidate)
        wave_ids.add(candidate.task_id)

    return wave


def _deps_satisfied(task: TaskSpec, completed: set[str]) -> bool:
    return all(dep in completed for dep in task.depends_on)


def _parse_depends_on(body: str) -> tuple[str, ...]:
    match = _DEPENDS_RE.search(body)
    if not match:
        return ()
    raw = match.group(1).strip()
    if re.fullmatch(r"(?i)none|n/?a|—|-|–", raw):
        return ()
    ids = _TASK_ID_TOKEN_RE.findall(raw)
    return tuple(dict.fromkeys(ids))


def _parse_where(body: str) -> str:
    match = _WHERE_RE.search(body)
    if not match:
        return ""
    return match.group(1).strip()


def _count_file_hints(where: str) -> int:
    if not where:
        return 0
    parts = re.split(r"[,;]|`|\band\b", where)
    count = 0
    for part in parts:
        token = part.strip().strip("`")
        if "/" in token or token.endswith((".dart", ".ts", ".tsx", ".py", ".yaml", ".yml", ".md", ".json")):
            count += 1
    return count


def _parse_gate_commands(body: str) -> tuple[str, ...]:
    commands: list[str] = []
    seen: set[str] = set()

    def add(command: str) -> None:
        normalized = _normalize_gate_command(command)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        commands.append(normalized)

    done_match = _DONE_WHEN_BLOCK_RE.search(body)
    if done_match:
        for match in _GATE_LINE_RE.finditer(done_match.group(1)):
            add(match.group(1))

    verify_match = _VERIFY_BLOCK_RE.search(body)
    if verify_match:
        block = verify_match.group(1)
        for match in _BACKTICK_RE.finditer(block):
            add(match.group(1))
        for line in block.splitlines():
            if "`" in line:
                continue
            stripped = line.strip()
            if _VERIFY_CMD_RE.fullmatch(stripped):
                add(stripped)

    return tuple(commands)


def _normalize_gate_command(command: str) -> str:
    text = command.strip().strip("`").strip()
    if not text:
        return ""
    match = _CMD_PREFIX_RE.match(text)
    if not match:
        return ""
    remainder = text[match.end() :].strip()
    prefix = match.group(1)
    if remainder:
        cut = re.search(r"[;`。]|(\sexit\b)|(\spass\b)|(\s—)|(\s-\s)", remainder, re.IGNORECASE)
        if cut:
            remainder = remainder[: cut.start()].strip()
    if remainder and not re.search(r"\s{2,}|\.\s+[A-ZÀ-Ú]", remainder):
        return f"{prefix} {remainder}".strip()
    if re.fullmatch(r"(?i)(?:dart|flutter)\s+analyze", prefix):
        return ""
    return prefix
