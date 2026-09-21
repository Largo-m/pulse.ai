#!/usr/bin/env python3
"""validate_validation.py — Feature Done gate for validation.md"""

import argparse
import os
import re
import sys

FILE_LINE_RE = re.compile(r"[\w./-]+\.\w+:\d+")
PASS_RE = re.compile(r"\bPASS\b", re.IGNORECASE)
FAIL_RE = re.compile(r"\bFAIL\b", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"\[(?:PASS/FAIL|feature|criterion)\]", re.IGNORECASE)


def resolve_report(target, root):
    if target:
        if os.path.isfile(target):
            return target
        if os.path.isdir(target):
            cand = os.path.join(target, "validation.md")
            if os.path.isfile(cand):
                return cand
            return _autodetect(target)
        cand = os.path.join(
            root, ".pulse", "specs", "features", target, "validation.md"
        )
        if os.path.isfile(cand):
            return cand
        return None
    return _autodetect(root)


def _autodetect(root):
    base = os.path.join(root, ".pulse", "specs", "features")
    if not os.path.isdir(base):
        return None
    hits = [
        os.path.join(base, d, "validation.md")
        for d in sorted(os.listdir(base))
        if os.path.isfile(os.path.join(base, d, "validation.md"))
    ]
    if len(hits) == 1:
        return hits[0]
    if len(hits) == 0:
        return None
    raise SystemExit(
        "validate_validation: multiple reports; pass one explicitly:\n  "
        + "\n  ".join(hits)
    )


def check(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    errors, warnings = [], []
    if PLACEHOLDER_RE.search(text) and "spec-defined outcome" in text.lower():
        warnings.append("report still looks like a template")
    if FAIL_RE.search(text) and not PASS_RE.search(text.split("## Summary")[-1] if "## Summary" in text else text):
        errors.append("verdict is FAIL or missing PASS in summary")
    overall = re.search(r"\*\*Overall\*\*\s*:?\s*([^\n]+)", text, re.IGNORECASE)
    verdict = re.search(r"\*\*Verdict\*\*\s*:?\s*([^\n]+)", text, re.IGNORECASE)
    line = ""
    if overall:
        line = overall.group(1)
    elif verdict:
        line = verdict.group(1)
    elif re.search(r"^#\s+.+\s+Validation", text, re.MULTILINE):
        head = text.splitlines()[0]
        line = head
    low = (line + "\n" + text[:800]).lower()
    if "fail" in low and "pass" not in low:
        errors.append("validation.md is not a PASS")
    if "pass" not in text.lower() and "ready" not in text.lower():
        errors.append("no PASS/Ready verdict found")
    if not FILE_LINE_RE.search(text):
        errors.append("no file:line evidence citations (evidence-or-zero)")
    return errors, warnings


def main(argv=None):
    p = argparse.ArgumentParser(prog="validate_validation.py")
    p.add_argument("target", nargs="?", default=None)
    p.add_argument("--root", default=".")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    path = resolve_report(args.target, args.root)
    if not path:
        print(
            "validate_validation: missing validation.md (feature is not done).",
            file=sys.stderr,
        )
        return 1

    errors, warnings = check(path)
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    fail = errors or (warnings and args.strict)
    print(
        f"\nvalidate_validation: {len(errors)} error(s), {len(warnings)} warning(s) in {path}"
    )
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
