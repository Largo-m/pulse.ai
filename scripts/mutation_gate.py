"""Fail when the parsers' mutation score drops below the floor (AGENTS.md §5.2).

Reads the stats `mutmut export-cicd-stats` writes after `mutmut run`. A mutant
that times out counts as killed: the tests noticed it. One with no test
covering it counts as survived, since nothing would notice that change either.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STATS = Path("mutants/mutmut-cicd-stats.json")


def score(stats: dict[str, int]) -> float:
    total = stats["total"] - stats.get("skipped", 0)
    caught = stats["killed"] + stats.get("timeout", 0)
    return 100.0 * caught / total if total else 100.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min", type=float, required=True, help="minimum score, in percent")
    args = parser.parse_args(argv)
    stats = json.loads(STATS.read_text(encoding="utf-8"))
    result = score(stats)
    print(f"mutation score {result:.1f}% (floor {args.min:.1f}%): {stats}")  # noqa: T201 - CLI report
    return 0 if result >= args.min else 1


if __name__ == "__main__":
    sys.exit(main())
