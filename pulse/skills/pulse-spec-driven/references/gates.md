# Deterministic Gates

Structural checks run in scripts so they do not depend on the model remembering a checklist. Judgment (is this AC precise? is this task the right slice?) still belongs to the agent.

Resolve `<skill-dir>` as the directory that contains this skill's `SKILL.md`. Project data stays under `.pulse/specs/` relative to the repo root (`--root` when cwd differs).

```
python3 <skill-dir>/scripts/validate_prd.py <feature-or-path>
python3 <skill-dir>/scripts/validate_tasks.py <feature-or-path>
python3 <skill-dir>/scripts/validate_validation.py <feature-or-path>
python3 <skill-dir>/scripts/validate_metrics.py <feature-or-path>
```

Exit non-zero = STOP and fix. Skip a script only when no code-execution tool exists; then perform the same checks by reading the artifact.

| Script | When | What |
| ------ | ---- | ---- |
| `validate_prd.py` | Before confirming spec (Medium+) | Required sections, EARS SHALL, ledger statuses, requirement IDs, motivating problem |
| `validate_tasks.py` | Before presenting tasks (Large/Complex) | Graph vs Depends on, Tests+Gate fields, no forward-phase deps |
| `validate_validation.py` | Before Feature Done | `validation.md` exists, verdict PASS, at least one `file:line` |
| `validate_metrics.py` | After Feature Done / spec change | METRICS.md current-feature table present |

Quick mode does not run these scripts. Medium without `tasks.md` skips `validate_tasks.py`.
