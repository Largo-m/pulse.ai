# Spec Change Protocol

Use when an approved spec, surface, test catalog, or task graph must change after work has started.

This is a first-class flow. Do not silently edit frozen contracts.

## When it applies

- A user decision contradicts an approved AC, story, or surface example
- Implementation discovers the spec is wrong, incomplete, or unsafe
- A requirement ID must be withdrawn, split, or have its outcome changed
- Task boundaries or test ownership no longer match the spec

## When it does not apply

- Fixing code to match the spec (that is Execute)
- Logging a Deferred Idea that is out of scope
- Marking a SPEC_DEVIATION for a local, justified implementation gap that does **not** change the user-visible contract — still record it, then decide whether a spec change is required

## Process

1. **Stop expanding implementation** of the disputed contract. Finish or revert in-flight edits that would encode the old meaning.
2. **Write a Spec Change record** in `PRD.md` under `## Spec Changes` (create the section if missing):

```markdown
### SC-NNN — [one-line change]

- **Date:** YYYY-MM-DD
- **Trigger:** [user decision | implementation discovery | review | verifier]
- **Was:** [IDs and the previous SHALL]
- **Becomes:** [new SHALL, withdrawn, or split into IDs]
- **Invalidates:** [task IDs, test IDs, design sections, review issues]
- **User:** confirmed via CLI | pending
```

3. **Confirm with the user** via [user-input.md](user-input.md) before rewriting frozen text, unless the user already ordered the change in this session (then record and apply).
4. **Rewrite only affected sections.** Preserve requirement IDs: never reuse a withdrawn ID; mark it `(withdrawn)` in the traceability table. New behavior gets a new ID.
5. **Invalidate downstream artifacts:**
   - `tests.md`: withdraw or replace assigned cases; do not renumber live IDs
   - `tasks.md`: set invalidated tasks back to pending or add fix tasks; update the graph
   - `TECHSPEC.md` / `surface.md` / `threat-model.md`: patch the owning section or note N/A
   - `validation.md`: treat prior PASS as stale until the Verifier re-runs
6. **Do not claim Feature Done** until the Verifier runs again on the new contract.

## ID rules

- Requirement IDs (`AUTH-01`) and test IDs (`UT-001`) are permanent once referenced by a task
- Withdraw in place; never recycle the number
- Spec Changes are append-only (`SC-001`, `SC-002`, …)

## Quick mode

Update `TASK.md` and re-collect CLI approval before further application-code edits. No SC-NNN table is required for a still-unapproved quick task.
