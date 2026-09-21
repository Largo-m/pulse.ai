# Execute

**Goal**: Implement ONE task at a time. Surgical changes. Verify. Repeat.

This is where code gets written. Every task follows the same cycle: plan → implement → verify. Verification is built into every task, not a separate phase.

**Git policy:** Do not commit and do not suggest commit messages unless the user explicitly asks for git help.

---

## MANDATORY: Before Starting Any Implementation

**Read [coding-principles.md](coding-principles.md) and state:**

1. **Assumptions** - What am I assuming? Any uncertainty?
2. **Files to touch** - List ONLY files this task requires
3. **Success criteria** - How will I verify this works?

⚠️ **Do not proceed without stating these explicitly.**

---

## Process

**Sub-agent context:** When this task is executed by a sub-agent, the sub-agent receives
the task definition, coding principles, TESTING.md, and relevant spec/design context.
All steps below apply identically whether running in the main context or a sub-agent.
The only difference: sub-agents report results back to the orchestrator rather than
continuing to the next task.

### 0. List Atomic Steps (MANDATORY when Tasks phase was skipped)

If there is no `tasks.md` for this feature, you MUST list atomic steps before writing any code. This is non-negotiable — it prevents the agent from losing focus and doing too many things at once.

```
## Execution Plan

1. [Step] → files: [list] → verify: [how]
2. [Step] → files: [list] → verify: [how]
3. [Step] → files: [list] → verify: [how]
```

**Each step must be:**

- ONE deliverable (one component, one function, one endpoint, one file change)
- Independently verifiable (can prove it works before moving on)

If listing steps reveals >5 steps or complex dependencies, STOP and create a formal `tasks.md` instead. The Tasks phase was wrongly skipped.

### 1. Pick Task

From tasks.md (if exists) or from the execution plan above. User specifies ("implement T3") or suggest next available.

### 2. Verify Dependencies

If tasks.md exists, check dependencies. If using inline plan, follow the order listed.

❌ If blocked: "T3 depends on T2 which isn't done. Should I do T2 first?"

### 3. State Implementation Plan

Before writing code:

```
Files: [list]
Approach: [brief description]
Success: [how to verify]
```

### 4. Write Tests First (RED)

If the task includes tests (per the Tests field in tasks.md or TESTING.md coverage matrix):

1. Write the test file(s) BEFORE writing any implementation
2. Tests must encode the expected behavior from the task's "Done when" criteria
3. Run the test command — confirm tests FAIL (RED state)
4. If tests pass before implementation exists, the tests are too weak — rewrite them

Tests MUST be derived from spec ACs / assigned test IDs — **not** from reading the implementation. Each assertion's value matches the spec-defined expected outcome. Where the spec is imprecise, flag a spec-precision gap instead of passing a vague assertion.

**Constraints:**

- Tests define correct behavior independently of implementation
- Each acceptance criterion from "Done when" maps to at least one test assertion
- Edge cases from spec.md that apply to this task get test cases too

If the task does NOT include tests (e.g., entity-only, config-only), skip to Step 4b.

### 4b. Implement (GREEN)

Write the minimum implementation needed to satisfy the task's success criteria: pass all relevant tests (when present) and meet the defined verification/gate checks when there are no direct tests.

**HARD CONSTRAINTS:**

- Do NOT modify tests written in Step 4. The tests are the spec — implementation conforms to them.
- Do NOT weaken assertions (making them less specific to pass more easily)
- Do NOT delete or skip test cases
- Do NOT use the test framework's skip/disable/pending mechanism to bypass failing tests
- Minimum code to pass — save structural improvements for a refactor task

If a test is genuinely wrong (tests the wrong behavior per spec), STOP and collect direction via [user-input.md](user-input.md) — never change test expectations without user confirmation.

Follow [coding-principles.md](coding-principles.md):

- Simplest code that works
- Touch ONLY listed files
- No scope creep

### 5. Gate Check (VERIFY)

Run the gate check command from the task definition. This is MANDATORY — not "if applicable."

1. Look up the command for the task's Gate level (quick/full/build) in TESTING.md's Gate Check Commands section, then run it
2. Non-zero exit code = STOP. Fix the failure. Re-run. Do not proceed until green.
3. Confirm the test count matches expectations (no tests were silently deleted or skipped)

**Tiered gates (from TESTING.md Gate Check Commands):**

| Task includes                    | Gate level | What runs                |
| -------------------------------- | ---------- | ------------------------ |
| Unit tests only                  | Quick      | Unit test command        |
| E2E or integration tests         | Full       | Unit + E2E commands      |
| Last task in a phase             | Build      | Build + lint + all tests |
| No tests (config, entities, etc) | Build      | Build + lint only        |

The gate check is deterministic. The test runner decides if the code is correct,
not the agent's self-assessment.

### 6. Post-Gate Review

After the gate check passes:

1. Verify test count: Are there at least as many test cases as before? (prevents silent deletion)
2. Verify no SPEC_DEVIATION: If implementation diverged from spec/design, add a marker:

```
// SPEC_DEVIATION: [what diverged]
// Reason: [why the deviation was necessary]
```

3. Quick complexity check: "Would senior engineer flag this as overcomplicated?"
   - Yes → Simplify, re-run gate
   - No → Proceed to update task status

4. **Task-layer evidence (cheap, author does this):** for each assigned AC / test ID, cite `file:line` of the assertion. A criterion with no citation is not covered. Full adequacy and mutation belong to the Verifier after the last task — do not run the four-table review on every task.

Contract conflicts: follow [invariants.md](invariants.md) precedence. Spec changes: [spec-change.md](spec-change.md).

### 7. Scope Guardrail

During implementation, you will notice things that could be improved, refactored, or added. **Do not act on them.** Instead:

- If it's a bug: note it in STATE.md as a blocker or use quick mode
- If it's an improvement: note it in STATE.md under "Deferred Ideas" or "Lessons Learned"
- If it's related to the current task: only include it if it's in the "Done when" criteria

**The heuristic:** "Is this in my task definition?" If no, don't touch it.

**Blast radius:** Approving Execute authorizes local edits only. Push, deploy, and production changes need an explicit go-ahead.

### 8. Update Task Status

Mark task complete in tasks.md. Update requirement traceability in spec.md if requirement IDs are used.

### 9. Feature-level validation (after the LAST task)

When every task is complete, Execute is not done. Dispatch a **fresh Verifier** (author ≠ verifier) per [validate.md](validate.md). Do not ask the user whether to run it. Then update [metrics.md](metrics.md) and distill [lessons.md](lessons.md) if there was signal. If the artifact matrix requires review, run [review.md](review.md) after a PASS.

---

## Execution Template

```markdown
## Implementing T[X]: [Task Title]

**Reading**: task definition from tasks.md
**Dependencies**: [All done? ✅ | Blocked by: TY]
**Tests**: [unit/e2e/integration/none]
**Gate**: [quick/full/build]

### Pre-Implementation (MANDATORY)

- **Assumptions**: [state explicitly]
- **Files to touch**: [list ONLY these]
- **Success criteria**: [how to verify]

### RED: Write Tests

- Test file(s): [paths]
- Test count: [N test cases]
- Confirmed failing: [Yes — all N tests fail as expected]

### GREEN: Implement

[Write minimum code to pass tests]

- Tests modified: None
- Tests skipped/deleted: None

### VERIFY: Gate Check

- Command: [gate check command]
- Result: [X passed, 0 failed]
- Test count: [N — matches RED phase count]

### Post-Gate

- [x] No SPEC_DEVIATION (or markers added)
- [x] No unnecessary changes made
- [x] Matches existing patterns

**Status**: ✅ Complete | ❌ Blocked | ⚠️ Partial
```

---

## Tips

- **One task at a time** — Focus prevents errors
- **Tools matter** — Wrong MCP = wrong approach
- **Reuses save tokens** — Copy patterns, don't reinvent
- **Verify before marking done** — Check all criteria, then update task status
- **Stay surgical** — Touch only what's necessary
- **No git operations** — Do not commit or suggest commit messages unless the user explicitly asks
- **Never "while I'm here"** — Scope creep during implementation is the #1 quality killer
- **Learn from mistakes** — If something goes wrong, add a Lesson Learned to STATE.md
