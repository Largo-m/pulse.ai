# Review Round

After Feature-layer validation PASSes, run a code review when the artifact matrix requires it (Large/Complex, or Medium with security/UI risk). The Verifier proves tests against the spec. Review proves the code.

Do not fix during review. Produce issue files; remediate in a second pass.

## Location

`.pulse/specs/features/[feature]/reviews-NNN/` with `issue_NNN.md`. Next round = max existing NNN + 1. Do not create the directory if there are no issues.

## Scope

Read spec.md, tests.md (if present), tasks.md, threat-model.md (if present), and the feature diff. Partition by task when the diff is large. Do not silently sample.

## Severity

- `critical` — security, data loss, crash, race on a hot path
- `high` — wrong behavior vs spec, user-visible reliability/performance
- `medium` — maintainability, missing non-blocking coverage
- `low` — naming, docs, optional cleanup

Skip issues already owned by the project linter/formatter.

## Issue file

```markdown
---
status: pending
file: path/to/file
line: 42
severity: high
round: 1
---

# Issue 001: [title ≤72 chars]

## Review Comment

[problem, evidence, suggested fix]

## Triage

- Decision: UNREVIEWED
- Notes:
```

`status`: `pending` → `valid` | `invalid` | `unresolved` | `blocked` → `resolved` after the fix is verified.

Deduplicate by root cause. One issue per distinct problem.

## Remediation

1. Triage every scoped issue before editing code
2. Fix `valid` issues in severity order; keep diffs on the listed files
3. Re-run the owning gate; do not weaken tests
4. Leave git to the user
5. Do not start another review inside the fix pass

Merge layer is not done while `critical` or `high` issues remain `pending` or `valid` without a user-accepted waiver.

## Visual contract

If a task named a visual reference, review checks that evidence exists at the owning boundary (reference vs implementation for the listed states/viewports) or that authorized deltas are recorded. Implementation-only screenshots do not prove parity.
