# SDD Metrics

Track whether the method is working. Write `.pulse/specs/project/METRICS.md` (create on first feature completion). Update at Feature Done and after each spec change or review round.

Do not invent numbers. If a count is unknown, write `unknown` and skip the claim.

## File

```markdown
# SDD Metrics

**Last Updated:** YYYY-MM-DD

## Current feature: [slug]

| Signal | Value |
| ------ | ----- |
| Spec changes (SC-NNN) | 0 |
| ACs without file:line evidence at verify | 0 |
| Surviving mutants | 0 |
| Sensor fallback used | no |
| Tasks reopened after "complete" | 0 |
| Review issues critical+high | 0 |
| Review issues marked invalid | 0 |
| Ledger rows still open at spec confirm | 0 |
| Lessons recorded this feature | 0 |

## Rolling (project)

| Feature | Verifier | Sensor | Review blocking | SC count |
| ------- | -------- | ------ | --------------- | -------- |
| [slug] | PASS/FAIL | killed/survived/fallback | 0 | 0 |
```

## When to write

| Event | Update |
| ----- | ------ |
| Spec confirmed | ledger open must be 0 |
| Verifier finishes | AC gaps, mutants, fallback |
| Spec change applied | increment SC count; mark prior PASS stale |
| Task reopened | increment reopened |
| Review round closed | blocking vs invalid counts |
| Lesson recorded | increment lessons |

A clean Feature PASS with no signal still gets a rolling row. That is the baseline, not a miss.

`python3 <skill-dir>/scripts/validate_metrics.py [feature]` checks the current-feature table exists and has no `open` ledger leftovers claimed as 0 when the spec still has `open` rows.
