from __future__ import annotations

from pathlib import Path


def print_workflow_banner(*, title: str, lines: list[str]) -> None:
    print()
    print(f"=== {title} ===")
    for line in lines:
        print(line)
    print()


def print_workflow_error(message: str) -> None:
    print(f"[pulse] {message}", flush=True)


def print_workflow_result(message: str) -> None:
    print(message)
