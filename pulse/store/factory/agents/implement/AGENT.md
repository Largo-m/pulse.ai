---
name: implement
description: Executa tasks.md
runtime: cursor
model: gpt-5.5
permission_policy: ask
---

# implement.md

# Execute

**Goal**: Implement ONE task at a time. Surgical changes. Verify. Repeat.

This is where code gets written. Every task follows the same cycle: plan → implement → verify. Verification is built into every task, not a separate phase.

**Unit tests only.** Execute writes implementation code and the unit tests that
prove it. Integration and end-to-end tests are **not** written here — they
belong to a later step, and writing them mid-implementation stretches a task
into wiring, fixtures and environment work that has nothing to do with the
deliverable. If a task cannot be proven by unit tests alone, say so, implement
it, and record the gap ([tasks.md](tasks.md), **Deferred test coverage**) instead
of reaching for an e2e suite.

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

### 4. Write Unit Tests First (RED)

If the task includes tests (per the Tests field in tasks.md or TESTING.md coverage matrix), those tests are **unit tests**. A task whose `Tests` field says `integration` or `e2e` was built under the old rule — treat it as `unit` for the parts you can cover that way and record the rest as deferred coverage.

1. Write the test file(s) BEFORE writing any implementation
2. Tests must encode the expected behavior from the task's "Done when" criteria
3. Run the test command — confirm tests FAIL (RED state)
4. If tests pass before implementation exists, the tests are too weak — rewrite them

Tests MUST be derived from spec ACs / assigned test IDs — **not** from reading the implementation. Each assertion's value matches the spec-defined expected outcome. Where the spec is imprecise, flag a spec-precision gap instead of passing a vague assertion.

**Constraints:**

- Tests define correct behavior independently of implementation
- Each acceptance criterion from "Done when" maps to at least one test assertion
- Edge cases from PRD.md that apply to this task get test cases too

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

1. Look up the command for the task's Gate level (quick/build) in TESTING.md's Gate Check Commands section, then run it
2. Non-zero exit code = STOP. Fix the failure. Re-run. Do not proceed until green.
3. Confirm the test count matches expectations (no tests were silently deleted or skipped)

**Tiered gates (from TESTING.md Gate Check Commands):**

| Task includes                    | Gate level | What runs                |
| -------------------------------- | ---------- | ------------------------ |
| Unit tests                       | Quick      | Unit test command        |
| Last task in a phase             | Build      | Build + lint + all tests |
| No tests (config, entities, etc) | Build      | Build + lint only        |

There is no Full gate in Execute: it existed to run the e2e suite a task had
just written, and tasks no longer write one. The Build gate still runs whatever
integration and e2e tests already exist in the repo — you just do not add to
them here.

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

Mark task complete in tasks.md. Update requirement traceability in PRD.md if requirement IDs are used.

### 9. Feature-level validation (after the LAST task)

When every task is complete, Execute is not done. Dispatch a **fresh Verifier** (author ≠ verifier) per [validate.md](validate.md). Do not ask the user whether to run it. Then update [metrics.md](metrics.md) and distill [lessons.md](lessons.md) if there was signal. If the artifact matrix requires review, run [review.md](review.md) after a PASS.

---

## Execution Template

```markdown
## Implementing T[X]: [Task Title]

**Reading**: task definition from tasks.md
**Dependencies**: [All done? ✅ | Blocked by: TY]
**Tests**: [unit/none]
**Gate**: [quick/build]

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

# validate.md

# Execute: Validate & Verify

**Goal**: Verify implementation meets spec AND coding principles. This is NOT a separate phase — verification is part of every task's completion within Execute.

**Three layers of verification** ([invariants.md](invariants.md) Definition of Done):

1. **Task (always, author):** "Done when" + assigned test IDs + gate exit 0. Cite `file:line` for each assigned AC. Cheap. Implementer runs it.

2. **Feature (always-on after last task, independent Verifier):** Author ≠ verifier. A fresh sub-agent (or a fresh-eyes pass with no inherited implementation notes) re-derives coverage from the spec. Writes `.pulse/specs/features/[feature]/validation.md`. Never prompted. Gaps become fix tasks; max **3** fix→re-verify loops then escalate.

3. **Merge (when the artifact matrix requires review):** [review.md](review.md) after Verifier PASS. Interactive UAT is extra for complex user-facing behavior.

**Author ≠ verifier:** the agent that wrote the code must not be the Feature-layer judge. If the harness cannot spawn a sub-agent, re-read PRD.md and the diff from scratch, ignore prior adequacy notes, and say so in `validation.md` (`Verifier: same-session fresh-eyes — harness had no sub-agent`). That fallback is weaker; do not pretend it is process isolation.

**Git policy:** Do not commit or suggest commit messages unless the user explicitly asks for git help.

**Trigger for explicit validation:** "Validate", "verify work", "UAT", "test with me", "walk me through it"

---

## Process

### 1. Check Completed Tasks

Go through tasks.md:

- [ ] All tasks marked done?
- [ ] Any blocked or partial?

### 2. Spec-anchored acceptance criteria (evidence-or-zero)

For each AC in PRD.md, the Verifier re-derives the spec-defined expected outcome:

```markdown
| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| WHEN X THEN Y | [precise value] | `path/to/test.ts:42` - `expect(...).toBe(...)` | PASS / GAP / spec-precision gap |
```

- An assertion must target the spec outcome, not merely exist
- No `file:line` → NOT covered
- Vague spec outcome → spec-precision gap, not a silent PASS
- Shallow patterns fail: tautologies, mock call counts instead of state, happy-path only when edges are listed
- An AC whose only coverage is a **Deferred test coverage** row in `tasks.md` is a GAP, not a PASS. Execute writes unit tests only ([implement.md](implement.md)); record the AC as uncovered and name the deferred ID, so the gap is counted rather than assumed away

### 3. Check Edge Cases

From PRD.md edge cases:

- [ ] [Edge case 1] handled correctly
- [ ] [Edge case 2] handled correctly

### 4. Run Build-Level Gate Check (MANDATORY)

Run the Build-level gate check from TESTING.md. This is NOT optional.

If TESTING.md does not exist (greenfield project), use the gate command agreed upon with the user during the Tasks phase.

1. Run: `[build gate command from TESTING.md, or the command agreed during planning]`
2. Non-zero exit code = STOP. Do not proceed to Code Quality Check.
3. Record results:
   - Total test count: [N]
   - Passed: [N]
   - Failed: [list]
   - Skipped: [list — each skip must be justified]

**Test Integrity Check:**

- Compare current test count against the count before this feature was implemented
- If test count DECREASED: investigate why. Tests should only be deleted with explicit justification.
- If assertions were weakened (less specific than before): flag as potential regression

### 5. Discrimination sensor (Feature layer)

Empirical check that tests can fail. **Never mutate the real worktree.**

1. Capture `git status --porcelain` baseline
2. Isolated scratch: `git worktree add <scratch> HEAD` (preferred). Fallback: copy affected files to a temp dir. **Forbidden:** `git stash`
3. Inject 1–3 behavior-level faults in the **new** code (flip condition, wrong return, off-by-one, remove a required side effect). P0 paths (auth, payments, data integrity): ≥5 faults or language mutation tooling if present
4. Run the Quick/Full gate against the scratch. Mutant must be **killed** (tests FAIL)
5. Discard scratch. Confirm real porcelain matches the baseline. If it differs, STOP, restore, treat the run as invalid
6. Surviving mutants → fix tasks (strengthen assertions). Do not mark Feature Done

**Fallback (honest):** if worktree/temp copy cannot run, write `Sensor: fallback — [why]` in `validation.md` and **do not** claim mutants were killed. Feature Done then requires user acceptance of the fallback or a later sensor run.

### 6. Code Quality Check (MANDATORY)

For each changed file, verify against [coding-principles.md](coding-principles.md):

| Check                                | Pass? |
| ------------------------------------ | ----- |
| No features beyond what was asked    |       |
| No abstractions for single-use code  |       |
| No unnecessary "flexibility" added   |       |
| Only touched files required for task |       |
| Didn't "improve" unrelated code      |       |
| Matches existing patterns/style      |       |
| Would senior engineer approve?       |       |

❌ Any "No"? → Fix before marking complete.

### 7. Interactive UAT (if user-facing feature)

For each testable deliverable, present one test at a time:

```
Test [N]: [Test Name]

Expected: [What should happen — specific and observable]

→ Does this work? Describe what you see.
```

Wait for user response:

| User says                      | Interpret as            |
| ------------------------------ | ----------------------- |
| "yes", "pass", "works", "next" | ✅ Pass                 |
| "skip", "can't test", "n/a"    | ⏭️ Skip                 |
| Anything else                  | ❌ Issue — log verbatim |

**Severity inference (never ask the user for severity):**

| User description contains               | Inferred severity |
| --------------------------------------- | ----------------- |
| crash, error, exception, fails, broken  | Blocker           |
| doesn't work, wrong, missing, can't     | Major             |
| slow, weird, off, minor, small          | Minor             |
| color, font, spacing, alignment, visual | Cosmetic          |
| (unclear)                               | Major (default)   |

### 8. Generate Fix Plans (if issues found)

For each issue from UAT or the Verifier:

1. **Diagnose** — Analyze the codebase to find root cause
2. **Create fix task** — Write a task definition with:
   - What: The specific fix
   - Where: File paths
   - Verify: How to prove the fix works
   - Done when: Acceptance criteria for the fix
3. **Present fix plan** — Show all fix tasks to user for approval

Fix tasks follow the same format as regular tasks and can be executed with the implement phase.

**Guardrail:** Maximum 3 diagnostic iterations per issue. The same bound applies to Verifier fix→re-verify. If gaps remain after 3 rounds, escalate.

### 9. Write validation.md + gates + lessons + metrics + review

The Verifier MUST write `.pulse/specs/features/[feature]/validation.md` (template below). Then:

1. `python3 <skill-dir>/scripts/validate_validation.py <feature>` — non-zero means Feature layer is not done
2. Distill grounded lessons ([lessons.md](lessons.md)) — clean PASS with no signal records nothing
3. Update [metrics.md](metrics.md) and run `validate_metrics.py`
4. If the artifact matrix requires it, run [review.md](review.md) (Merge layer)

Return a compact chat summary: PASS/FAIL, AC coverage, sensor killed/survived/fallback, report path, ranked gaps.

---

## Validation Report Template

```markdown
# [Feature] Validation

**Date**: [YYYY-MM-DD]
**Spec**: `.pulse/specs/features/[feature]/PRD.md`
**Diff range**: [commits or branch..HEAD]
**Verifier**: independent sub-agent | same-session fresh-eyes (harness had no sub-agent)
**Verdict**: PASS | FAIL

---

## Task Completion

| Task | Status     | Notes   |
| ---- | ---------- | ------- |
| T1   | ✅ Done    | -       |
| T2   | ✅ Done    | -       |
| T3   | ⚠️ Partial | [Issue] |

---

## Spec-Anchored Acceptance Criteria

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| WHEN X THEN Y | [precise value] | `path:42` - `expect(...)` | PASS |

**Status**: All ACs covered / Gaps present / Spec-precision gaps

## Discrimination Sensor

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| 1 | `src/a.ts:10` | flipped condition | Killed |

**Sensor depth**: lightweight / P0-full / fallback — [reason]
**Result**: [N/N killed] PASS | FAIL | fallback

---

## Interactive UAT Results (if performed)

| #   | Test        | Result   | Details                                         |
| --- | ----------- | -------- | ----------------------------------------------- |
| 1   | [Test name] | ✅ Pass  | -                                               |
| 2   | [Test name] | ❌ Issue | [Verbatim user response] — Severity: [inferred] |
| 3   | [Test name] | ⏭️ Skip  | [Reason]                                        |

---

## Code Quality

| Principle        | Status |
| ---------------- | ------ |
| Minimum code     | ✅     |
| Surgical changes | ✅     |
| No scope creep   | ✅     |
| Matches patterns | ✅     |

---

## Edge Cases

- [x] Edge case 1: Handled correctly
- [ ] Edge case 2: NOT handled - needs fix

---

## Tests

- **Gate command**: [full command]
- **Result**: [X] passed, [Y] failed, [Z] skipped
- **Test count before feature**: [N]
- **Test count after feature**: [M]
- **Delta**: [+(M - N) new tests]
- **Skipped tests**: [list with justification for each]
- **Failures**: [list with details]

---

## Fix Plans (if issues found)

### Fix 1: [Issue description]

- **Root cause**: [What's actually wrong]
- **Fix task**: [Task definition]
- **Priority**: [Blocker/Major/Minor/Cosmetic]

---

## Requirement Traceability Update

Update PRD.md requirement statuses:

| Requirement | Previous Status | New Status   |
| ----------- | --------------- | ------------ |
| [FEAT]-01   | Implementing    | ✅ Verified  |
| [FEAT]-02   | Implementing    | ❌ Needs Fix |

---

## Summary

**Overall**: PASS | FAIL
**Spec-anchored check**: [N/N ACs | M spec-precision gaps]
**Sensor**: [N/N killed | fallback]
**Gate**: [X passed]

**What works**: [List]

**Issues found**: [Issue 1: How to fix]

**Next steps**: [Action]
```

---

## Tips

- **P1 first** — MVP must work before P2/P3
- **WHEN/THEN = Test** — Each criterion is a test case
- **Be specific** — "Doesn't work" isn't helpful
- **Recommend fixes** — Don't just report problems, create fix tasks
- **Quality check is mandatory** — Not optional
- **Infer severity** — Never ask the user "how bad is this?"
- **Max 3 diagnostic iterations** — Prevents infinite investigation loops
- **Update traceability** — Every verified requirement updates PRD.md status
- **Always write validation.md** — Feature Done is a file, not a chat claim
- **Sensor in scratch only** — never stash; fallback must be labeled
- **Review after PASS** — Verifier does not replace code review when the matrix requires it

# coding-principles.md

# Coding Principles

Behavioral bias, not checklist. Read before every implementation.

---

## Before Coding

- State assumptions explicitly. If uncertain, stop and collect input via [user-input.md](user-input.md).
- Multiple interpretations exist? Present all—don't pick silently. Follow [invariants.md](invariants.md) precedence; never let code silently beat an approved spec.
- Spec must change? [spec-change.md](spec-change.md). Do not rewrite the spec to match the implementation.
- Simpler approach exists? Say so. Push back when warranted.
- Something unclear? Stop. Name what's confusing. Collect input via [user-input.md](user-input.md).
- User's approach seems wrong? Disagree honestly. Don't be sycophantic.

---

## During Implementation

### Simplicity

- No features beyond what was asked
- No abstractions for single-use code
- No "flexibility" or "configurability" not requested
- No error handling for impossible scenarios
- 200 lines that could be 50? Rewrite it.

### Surgical Changes

- Don't "improve" adjacent code, comments, or formatting
- Don't refactor things that aren't broken
- Match existing style, even if you'd do differently
- Unrelated dead code noticed? Mention it—don't delete it
- Remove ONLY imports/variables/functions YOUR changes orphaned
- Don't remove pre-existing dead code unless asked

### Test Integrity

- NEVER weaken an existing test assertion to make it pass
- NEVER delete a test to reduce failure count
- NEVER use the test framework's skip/disable/pending mechanism to bypass a failing test
- NEVER modify tests written in the RED phase during GREEN phase
- If a test is genuinely wrong, STOP and confirm with the user before changing it
- Tests are the spec — implementation conforms to tests, not the other way around

### Goal-Driven

- Transform vague tasks into verifiable goals
- Multi-step work? State brief plan with verify checkpoints
- Every changed line must trace directly to user's request

---

## After Each Change

Ask: "Would senior engineer call this overcomplicated?"
If yes → simplify before proceeding.

# state-management.md

# State Management

**Purpose:** Persistent memory across sessions - decisions, blockers, learnings.

## Structure

**Output:** `.pulse/specs/project/STATE.md`

```markdown
# State

**Last Updated:** [ISO timestamp]
**Current Work:** [Feature name] - [Task identifier]

---

## Recent Decisions (Last 60 days)

### AD-[NNN]: [Decision title] ([date])

**Decision:** [What was decided]
**Reason:** [Why this choice]
**Trade-off:** [What was sacrificed]
**Impact:** [How this affects implementation]

### AD-[NNN]: [Decision title] ([date])

[Same structure]

---

## Active Blockers

### B-[NNN]: [Blocker description]

**Discovered:** [Date]
**Impact:** [Severity and scope]
**Workaround:** [Temporary solution if available]
**Resolution:** [Path to permanent fix]

---

## Lessons Learned

### L-[NNN]: [Learning description]

**Signal:** ac_gap | surviving_mutant | spec_precision_gap | spec_deviation | gate_fail | review_valid
**Source:** [file:line or AC id]
**Feature:** [slug]
**Status:** candidate | confirmed | quarantined
**Context:** [Situation that occurred]
**Problem:** [What went wrong]
**Solution:** [How it was resolved]
**Prevents:** [What this knowledge prevents in future]

---

## Quick Tasks

| #   | Description              | Date   | Spec                         | Status                |
| --- | ------------------------ | ------ | ---------------------------- | --------------------- |
| 001 | [Quick task description] | [date] | `.pulse/specs/quick/001-slug/`     | ⏳ Awaiting Approval  |
| 002 | [Quick task description] | [date] | `.pulse/specs/quick/002-slug/`     | ✅ Done               |

---

## Deferred Ideas

Ideas captured during work that belong in future features or phases. Prevents scope creep while preserving good ideas.

- [ ] [Idea description] — Captured during: [feature/phase]
- [ ] [Idea description] — Captured during: [feature/phase]

---

## Todos

Capture in-progress thoughts and action items that don't fit in active tasks.

- [ ] [TODO: action item]
- [ ] [TODO: action item]
```

## When to Update

| Event                            | Action                                 |
| -------------------------------- | -------------------------------------- |
| Significant architectural choice | Add AD-[NNN]                           |
| Implementation blocked           | Add B-[NNN]                            |
| Important discovery/learning     | Add L-[NNN] with **Signal** + **Source** ([lessons.md](lessons.md)) |
| Quick task started (plan ready)  | Create `.pulse/specs/quick/NNN-slug/TASK.md`, update Current Work, add Quick Tasks row ⏳ |
| Quick task completed             | Update TASK.md, create SUMMARY.md, set Quick Tasks row ✅ Done          |
| Scope creep captured             | Add to Deferred Ideas                  |
| In-progress thought              | Add to Todos                           |
| Session end                      | Update "Last Updated" + "Current Work" |

## Size Management (Hybrid Strategy)

**Zones:**

- 🟢 <7k tokens: No action
- 🟡 7-10k tokens: Footer note "STATE.md at [X]k. Cleanup recommended."
- 🔴 >10k tokens: Active prompt "STATE.md critical ([X]k). Cleanup now?"

**Cleanup process:**

- Move decisions >60 days to STATE-ARCHIVE.md
- Keep only active blockers
- Preserve recent learnings (<60 days)

**Validation:**

- Decisions have clear rationale?
- Blockers include resolution path?
- Learnings are actionable?

---

## Preferences

Track user-facing behavioral state in STATE.md:

```markdown
## Preferences

**Model Guidance Shown:** [ISO date or "never"]
```

**Update when:**

| Event                       | Action                   |
| --------------------------- | ------------------------ |
| First model tip given       | Set date                 |
| User acknowledges/dismisses | Keep date (don't repeat) |

This prevents repetitive suggestions while maintaining natural, helpful behavior.
