#!/usr/bin/env python3
"""validate_metrics.py — METRICS.md current-feature table exists"""

import argparse
import os
import re
import sys


def resolve_metrics(root):
    path = os.path.join(root, ".pulse", "specs", "project", "METRICS.md")
    return path if os.path.isfile(path) else None


def check(path, feature):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    errors, warnings = [], []
    if "## Current feature:" not in text:
        errors.append("missing ## Current feature section")
    if feature:
        if feature.lower() not in text.lower():
            warnings.append(f"current feature slug '{feature}' not mentioned")
    required_signals = [
        "Spec changes",
        "ACs without file:line",
        "Surviving mutants",
        "Tasks reopened",
        "Review issues critical",
    ]
    for sig in required_signals:
        if sig.lower() not in text.lower():
            errors.append(f"missing signal row: {sig}")
    if re.search(r"\bunknown\b", text, re.IGNORECASE):
        warnings.append("one or more signals are unknown")
    return errors, warnings


def main(argv=None):
    p = argparse.ArgumentParser(prog="validate_metrics.py")
    p.add_argument("target", nargs="?", default=None)
    p.add_argument("--root", default=".")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    path = resolve_metrics(args.root)
    if not path:
        print(
            "validate_metrics: missing .pulse/specs/project/METRICS.md",
            file=sys.stderr,
        )
        return 1

    errors, warnings = check(path, args.target)
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    fail = errors or (warnings and args.strict)
    print(
        f"\nvalidate_metrics: {len(errors)} error(s), {len(warnings)} warning(s) in {path}"
    )
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
