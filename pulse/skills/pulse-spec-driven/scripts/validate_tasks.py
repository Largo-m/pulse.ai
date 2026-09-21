#!/usr/bin/env python3
"""validate_tasks.py — graph + Tests/Gate checks for .pulse/specs/features/<feature>/tasks.md"""

import argparse
import os
import re
import sys

TASK_HEAD_RE = re.compile(r"^#{2,4}\s+(T\d+)\s*:", re.IGNORECASE)
EDGE_RE = re.compile(r"\bT\d+\b", re.IGNORECASE)
GRAPH_NODE_RE = re.compile(r"^\s*-\s+id:\s*(T\d+)\s*$", re.IGNORECASE)
GRAPH_EDGE_RE = re.compile(
    r"^\s*-\s+\{\s*from:\s*(T\d+)\s*,\s*to:\s*(T\d+)\s*\}\s*$", re.IGNORECASE
)
YAML_EDGE_RE = re.compile(
    r"from:\s*(T\d+).*to:\s*(T\d+)|to:\s*(T\d+).*from:\s*(T\d+)", re.IGNORECASE
)


def resolve_tasks(target, root):
    if target:
        if os.path.isfile(target):
            return target
        if os.path.isdir(target):
            cand = os.path.join(target, "tasks.md")
            if os.path.isfile(cand):
                return cand
            return _autodetect(target)
        cand = os.path.join(root, ".pulse", "specs", "features", target, "tasks.md")
        if os.path.isfile(cand):
            return cand
        return None
    return _autodetect(root)


def _autodetect(root):
    base = os.path.join(root, ".pulse", "specs", "features")
    if not os.path.isdir(base):
        return None
    features = [
        d
        for d in sorted(os.listdir(base))
        if os.path.isfile(os.path.join(base, d, "tasks.md"))
    ]
    if len(features) == 1:
        return os.path.join(base, features[0], "tasks.md")
    if len(features) == 0:
        return None
    raise SystemExit(
        "validate_tasks: multiple features found; pass one explicitly:\n  "
        + "\n  ".join(os.path.join(base, f, "tasks.md") for f in features)
    )


def section_present(lines, name):
    return any(
        re.match(r"^#{1,4}\s+" + re.escape(name) + r"\b", ln.strip()) for ln in lines
    )


def parse_task_blocks(lines):
    tasks = {}
    current = None
    buf = []
    for ln in lines:
        m = TASK_HEAD_RE.match(ln)
        if m:
            if current:
                tasks[current] = buf
            current = m.group(1).upper()
            buf = [ln]
        elif current:
            buf.append(ln)
    if current:
        tasks[current] = buf
    return tasks


def field(block, name):
    pat = re.compile(r"^\*\*" + re.escape(name) + r"\*\*\s*:?\s*(.*)$", re.IGNORECASE)
    for ln in block:
        m = pat.match(ln.strip())
        if m:
            return m.group(1).strip()
    return None


def depends_ids(text):
    if not text or text.lower() in {"none", "-", "n/a"}:
        return set()
    return {x.upper() for x in EDGE_RE.findall(text)}


def parse_graph(text):
    nodes = set()
    edges = set()
    in_graph = False
    for ln in text.splitlines():
        if re.match(r"^#{1,4}\s+Task Graph\b", ln.strip()):
            in_graph = True
            continue
        if in_graph and re.match(r"^#{1,4}\s+\S", ln):
            break
        if not in_graph:
            continue
        nm = GRAPH_NODE_RE.match(ln)
        if nm:
            nodes.add(nm.group(1).upper())
            continue
        em = GRAPH_EDGE_RE.match(ln)
        if em:
            edges.add((em.group(1).upper(), em.group(2).upper()))
            continue
        ym = YAML_EDGE_RE.search(ln)
        if ym:
            a = (ym.group(1) or ym.group(4) or "").upper()
            b = (ym.group(2) or ym.group(3) or "").upper()
            if a and b:
                edges.add((a, b))
    return nodes, edges


def check(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    lines = text.splitlines()
    errors, warnings = [], []

    for name in ("Execution Plan", "Task Breakdown"):
        if not section_present(lines, name):
            errors.append(f"missing required section: {name}")

    if not section_present(lines, "Task Graph"):
        errors.append("missing required section: Task Graph (parseable nodes/edges)")

    tasks = parse_task_blocks(lines)
    if not tasks:
        errors.append("no T[n] task headings found")

    graph_nodes, graph_edges = parse_graph(text)
    body_edges = set()

    for tid, block in tasks.items():
        tests = field(block, "Tests")
        gate = field(block, "Gate")
        where = field(block, "Where")
        deps = field(block, "Depends on")
        if not tests:
            errors.append(f"{tid}: missing Tests field")
        if not gate:
            errors.append(f"{tid}: missing Gate field")
        if tests and tests.lower() == "none":
            warnings.append(f"{tid}: Tests: none — confirm coverage matrix")
        if where and "," in where:
            warnings.append(f"{tid}: Where names multiple files (granularity smell)")
        for dep in depends_ids(deps or ""):
            body_edges.add((dep, tid))

    if graph_nodes and set(tasks) - graph_nodes:
        missing = ", ".join(sorted(set(tasks) - graph_nodes))
        errors.append(f"Task Graph nodes missing tasks: {missing}")
    if graph_nodes - set(tasks):
        extra = ", ".join(sorted(graph_nodes - set(tasks)))
        errors.append(f"Task Graph has unknown nodes: {extra}")

    if graph_edges or body_edges:
        only_graph = graph_edges - body_edges
        only_body = body_edges - graph_edges
        if only_graph:
            errors.append(
                "graph edge without Depends on: "
                + ", ".join(f"{a}->{b}" for a, b in sorted(only_graph))
            )
        if only_body:
            errors.append(
                "Depends on without graph edge: "
                + ", ".join(f"{a}->{b}" for a, b in sorted(only_body))
            )

    return errors, warnings


def main(argv=None):
    p = argparse.ArgumentParser(prog="validate_tasks.py")
    p.add_argument("target", nargs="?", default=None)
    p.add_argument("--root", default=".")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    path = resolve_tasks(args.target, args.root)
    if not path:
        print(
            "validate_tasks: could not locate tasks.md under .pulse/specs/features/.",
            file=sys.stderr,
        )
        return 2

    errors, warnings = check(path)
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  ERROR {e}")
    fail = errors or (warnings and args.strict)
    print(f"\nvalidate_tasks: {len(errors)} error(s), {len(warnings)} warning(s) in {path}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
