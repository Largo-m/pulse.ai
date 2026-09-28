# Test Catalog

`.pulse/specs/features/[feature]/tests.md` is the test contract. PRD writes it for Large/Complex (and for Medium when there is a public surface). `cy`-style IDs stay stable: implementers write exactly the assigned cases; the Verifier and review check the suite against this file.

Medium with no public surface may keep cases inline in PRD.md ACs; still assign IDs when tasks exist.

## ID rules

- `UT-NNN` unit, `IT-NNN` integration, `E2E-NNN` end-to-end — zero-padded, sequential per prefix
- Permanent once a task references them: never renumber or reuse. Mark dropped cases `(withdrawn)`
- Assign every live ID to **exactly one** task — the task that completes that behavior
- Reuse existing coverage by path + invariant; do not create tests just to fill a template

## Skeleton

```markdown
# Test Specification: [Feature]

Companion to PRD.md. Derived from stories, surface.md (if present), and design.

## Strategy

- Frameworks / harnesses:
- How unit / integration / e2e run in this repo:
- Conventions:

## Coverage Matrix

| Source | Behavior | Unit | Integration | E2E |
| ------ | -------- | ---- | ----------- | --- |
| [FEAT]-01 | [summary] | UT-001 | IT-001 | E2E-001 |
| [FEAT]-01 edge | [edge] | UT-002 | — | — |

## Unit Tests

- **UT-001** (happy): [target] — given [input], produces [exact output]
- **UT-002** (error): [target] — given [invalid], returns [exact error]

## Integration Tests

- **IT-001**: [wired components] — setup; action; observable result

## End-to-End Tests

- **E2E-001**: [entry from surface.md] → steps → final observable outcome
```

## Case-writing rules

- Concrete or nothing: real function/route/command, actual input, exact expected result
- Tag unit cases: `happy`, `error`, `boundary`, `concurrency`, `idempotency`, `ordering`, `state`
- One observable behavior per case
- Unit fakes only I/O. Integration uses real wiring. E2E goes through the public surface
- Every story and listed edge has a row whose owner is a test ID, cited existing coverage, or a one-line reason no automated test is needed

## Gates

Infer run commands from the repo (`TESTING.md`, package scripts, Makefile, CI). Render into `tasks.md`:

```markdown
## Test Coverage Matrix

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |

## Gate Check Commands

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | unit only | |
| Full | integration/e2e | |
| Build | phase end or no tests | |
```

Co-locate tests with the code task. Tests are not a separate task.
