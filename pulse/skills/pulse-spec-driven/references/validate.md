# Execute: Validate & Verify

**Goal**: Verify implementation meets spec AND coding principles. This is NOT a separate phase — verification is part of every task's completion within Execute.

**Three layers of verification** ([invariants.md](invariants.md) Definition of Done):

1. **Task (always, author):** "Done when" + assigned test IDs + gate exit 0. Cite `file:line` for each assigned AC. Cheap. Implementer runs it.

2. **Feature (always-on after last task, independent Verifier):** Author ≠ verifier. A fresh sub-agent (or a fresh-eyes pass with no inherited implementation notes) re-derives coverage from the spec. Writes `.pulse/specs/features/[feature]/validation.md`. Never prompted. Gaps become fix tasks; max **3** fix→re-verify loops then escalate.

3. **Merge (when the artifact matrix requires review):** [review.md](review.md) after Verifier PASS. Interactive UAT is extra for complex user-facing behavior.

**Author ≠ verifier:** the agent that wrote the code must not be the Feature-layer judge. If the harness cannot spawn a sub-agent, re-read spec.md and the diff from scratch, ignore prior adequacy notes, and say so in `validation.md` (`Verifier: same-session fresh-eyes — harness had no sub-agent`). That fallback is weaker; do not pretend it is process isolation.

**Git policy:** Do not commit or suggest commit messages unless the user explicitly asks for git help.

**Trigger for explicit validation:** "Validate", "verify work", "UAT", "test with me", "walk me through it"

---

## Process

### 1. Check Completed Tasks

Go through tasks.md:

- [ ] All tasks marked done?
- [ ] Any blocked or partial?

### 2. Spec-anchored acceptance criteria (evidence-or-zero)

For each AC in spec.md, the Verifier re-derives the spec-defined expected outcome:

```markdown
| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| WHEN X THEN Y | [precise value] | `path/to/test.ts:42` - `expect(...).toBe(...)` | PASS / GAP / spec-precision gap |
```

- An assertion must target the spec outcome, not merely exist
- No `file:line` → NOT covered
- Vague spec outcome → spec-precision gap, not a silent PASS
- Shallow patterns fail: tautologies, mock call counts instead of state, happy-path only when edges are listed

### 3. Check Edge Cases

From spec.md edge cases:

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
**Spec**: `.pulse/specs/features/[feature]/spec.md`
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

Update spec.md requirement statuses:

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
- **Update traceability** — Every verified requirement updates spec.md status
- **Always write validation.md** — Feature Done is a file, not a chat claim
- **Sensor in scratch only** — never stash; fallback must be labeled
- **Review after PASS** — Verifier does not replace code review when the matrix requires it
