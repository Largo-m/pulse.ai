---
name: review-fix
description: Tria e corrige as findings da rodada de review
runtime: cursor
model: Auto
permission_policy: ask
---

# review-fix.md

# Review Fix

**Goal**: Resolve what the review found, and nothing else.

The round file is the entire scope and the only artifact you touch.

This is the second half of the Merge layer. The review step identifies; this one
repairs. They are separate steps, in separate sessions, so that the repair cannot
quietly become the next review.

---

## Non-Negotiables

1. **Never generate a review here.** Something you notice while fixing is not
   yours to raise. If it is genuinely `critical`, tell the user in your report
   and let them decide; do not add a finding, and do not open a round. This
   separation is the whole reason the review terminates.
2. **Triage everything before editing any code.** Partial context produces fixes
   that fight each other.
3. **Never weaken a test to make it pass.** Deleting an assertion, loosening a
   matcher, adding a skip, or widening a tolerance so the suite goes green is the
   single worst outcome of this pass. It converts a real finding into a silent
   one.
4. **Never revert a fix to pass verification.** Find the root cause. If
   verification fails on pre-existing code unrelated to your change, document it
   and proceed.
5. **Scope is locked to the files the findings name.** If a fix genuinely
   requires another file, make the minimum change and say why in that finding's
   `Triagem:`.
6. **No refactoring on the side.** Cleanup you noticed is not part of this pass.
   It is a deferred idea in `STATE.md`.
7. **Triage honestly.** `invalid` is not a workload reduction tool. The rate
   decides how aggressive the next review is allowed to be: above 30%, the
   reviewer loses passes E and F. Gaming it today buys a noisier review tomorrow,
   and your report has to state the rate out loud.
8. **Git stays with the user.** No commits, no staging, no suggested commit
   messages, no pushes.

---

## Process

### 0. Load the round

List `.pulse/specs/features/<feature>/reviews/` and read the whole round file
before anything else, plus the artefacts the findings cite: `PRD.md` for Pass A
findings, `tasks.md` or `TESTING.md` for Pass B, `threat-model.md` for Pass D,
`CONVENTIONS.md` for Pass E.

**The round file is the resume point.** A `pending` finding is remaining work.
Interrupting this pass and picking it up in another session needs no handoff note
beyond the file itself.

If every finding is already settled, say so and stop.

### 1. Triage every finding

**Read [triage.md](triage.md) now.** No code is edited in this step.

Change the status token in the heading and write the reasoning in `Triagem:`.

```
### F1 · critical · pending     →     ### F1 · critical · valid
```

| Status | Means |
| --- | --- |
| `valid` | real problem, will be fixed in this pass |
| `invalid` | not a real problem; `Triagem:` explains why, concretely |
| `unresolved` | real, but needs an external change or an out-of-scope dependency |
| `blocked` | cannot proceed; `Triagem:` names the blocker |
| `declined-accepted` | the author declined, the reasoning held, dropped permanently |

Status lives only in the heading. Do not add it to the index table.

### 2. Fix, in severity order

**Read [fixing.md](fixing.md) now.**

`critical` first, then `high`, `medium`, `low`. Severity order means the most
impactful repairs land even if the pass is interrupted.

For each `valid` finding: name the invariant that changed and its owning suite,
implement the production-quality fix, and record where it lives.

When one fix resolves another finding, mark both, citing the same change. Do not
fix the same root cause twice.

Follow [coding-principles.md](coding-principles.md) — the same bias the
implementation phase works under. A review fix is still code, and the simplest
repair that holds is still the right one.

### 3. Verify

Run the real checks that own the behavior you changed, using the gate commands in
`.pulse/specs/codebase/TESTING.md` when it exists. Reuse valid evidence for
unchanged inputs; do not invent an extra full local run.

Failure handling, in order:

1. Failure caused by your fix: find the root cause and fix it.
2. Failure in pre-existing code unrelated to your change: document it in the
   relevant `Triagem:` and proceed.
3. Two fixes conflicting: after **two** attempts, document the conflict in both
   findings and report it. Do not loop.

If the sandbox will not run the project's checks, say which check could not run
and why, in the report and in the relevant `Triagem:`. Never describe a repair as
verified when nothing ran.

### 4. Close out

**Read [closeout.md](closeout.md) now.**

- Fixed finding → `resolved`, with `- **Fix:** \`path:line\`` pointing at where
  the repair lives. Open that file and confirm the line is really there.
- Update `counts` and `verdict` in the frontmatter. The verdict is derived from
  what remains **open**; a `critical` that is now `resolved` or `invalid` no
  longer blocks.
- If every finding was `invalid` and no code changed, say so and stop. Do not
  manufacture a change.

### 5. Self-check (MANDATORY)

There is no script to run this for you, so run it yourself against
[closeout.md](closeout.md). Every item is a rejection, not a suggestion:

1. No finding is still `pending` or `valid` — neither is terminal.
2. Every `resolved` has a `Fix:` whose `path:line` exists on disk.
3. Every `invalid` carries real reasoning, not "não procede" or "false positive".
4. `counts` still matches the findings in the file.
5. `verdict` is recomputed from what is open, by the table in
   [closeout.md](closeout.md).
6. IDs, the index table, and the finding bodies are untouched.
7. No finding was added.

Then compute the dismissal rate: `invalid` over total. Above 50% it goes in the
report with a sentence explaining it — either the review was noisy, which the
calibration loop should know, or the triage was generous with itself, which the
user should know.

### 6. Promote

Look at what was fixed. Any finding that is deterministic by nature (a banned
pattern, a naming rule, something a linter could catch) goes into
`## Promover a convenção`, and from there into `STATE.md` as a confirmed lesson
and `CONVENTIONS.md` as a rule.

This is the only part of the cycle that makes the next review cheaper than this
one. Do not skip it because the fixes are done.

### 7. Report

State plainly, in this order:

1. What was fixed, by severity.
2. What was dismissed and the strongest reason why, plus the dismissal rate.
3. What remains open, and what it needs (a waiver, a decision, an external
   change).
4. Whether the Merge layer is unblocked, in those words.
5. Anything you noticed that is not in the file, flagged as **not a finding**.

If `critical` or `high` findings remain open without a user waiver, **the Merge
layer is not done.** Say that without hedging.

Then stop. Git is the user's.

---

## Waivers and deferrals

A finding the user chooses not to fix needs their explicit decision. Ask for it —
asking does not end this step, and a question is always cheaper than a guess.
Never assume a waiver.

- **Waived:** the user accepts the risk. Record `declined-accepted` with their
  reason in `Triagem:`.
- **Deferred:** the work is real but not now. It becomes a deferred idea in
  `STATE.md` with a pointer to the round file, and the finding is `unresolved`
  naming that entry.

Both are terminal. Neither keeps the round open.

If there is nobody to ask, leave the finding `unresolved` and let the step close
`blocked`, naming the decision that is missing. A waiver nobody gave is not a
waiver.

---

## What this step does not do

- Produce findings. That is the review step.
- Decide whether to merge. It reports whether the findings allow it; the user
  merges.
- Touch git in any way.
- Run a fourth round. There is no fourth round.

---

## Error Handling

- Round file missing: say so and close. There is nothing to remediate without
  findings, and a clean review legitimately leaves none.
- A finding cites a file that no longer exists: triage it `invalid` and say the
  code was removed or moved, naming where it went.
- An unfinished status survives your self-check: that is correct behavior, not a
  false alarm. Finish the triage.
- No way to run the project's checks: report which fixes are unverified. Do not
  claim verification that did not happen.

# triage.md

# Triage

Load at Step 1. **No code is edited during triage.** Every finding gets a verdict
before any file changes, because a fix written with partial context is a fix that
fights the next one.

## The decision

For each finding, answer one question: **is this a real problem in this codebase,
right now?**

Not "is it worth fixing" (that is severity, already assigned). Not "do I want to
fix it" (that is not a question). Just: is the claim true.

| Status | When | `Triagem:` must contain |
| --- | --- | --- |
| `valid` | the claim is true and you will fix it in this pass | the root cause and the intended fix |
| `invalid` | the claim is false, or true of code that no longer exists | why, concretely, with evidence |
| `unresolved` | true, but the fix needs an external change or an out-of-scope dependency | the named dependency |
| `blocked` | true, but something prevents proceeding | the named blocker |
| `declined-accepted` | the author declined, and the reasoning held | the author's reason, and why it holds |

## How to verify a claim before accepting it

The review verified its own citations against disk, so the line exists and says
what the finding says. That is not the same as the finding being right. Check the
reasoning:

1. **Read the cited code and its callers.** The finding names a triggering input;
   can that input actually reach this code?
2. **Check the contract.** For a Pass A finding, read the requirement in `PRD.md`
   yourself. Reviews misread specs.
3. **Check for existing coverage.** A test that already pins the behavior means
   the finding is about a path the suite covers; that changes the fix, and
   sometimes kills the finding.
4. **Check for an intentional choice.** An adjacent comment explaining the
   trade-off, a decision in `TECHSPEC.md`, or an entry in the Ambiguity Ledger
   can make suspicious code correct. The review was told to look for this and may
   have missed it.
5. **Check `CONCERNS.md`.** A finding in a component already documented as
   fragile is more likely real, not less.

## Writing an honest `invalid`

`invalid` is the status with the most leverage and the most room for
self-deception. It silences a finding permanently and it decides whether the next
review is allowed to run its subjective passes at all.

Write at least a couple of real sentences. A bare dismissal is not a triage.

**Not a triage:** "não procede", "falso positivo", "works as intended", "by
design".

**A triage:** name what the review got wrong and show it.

> `getUser` nunca recebe `null` aqui: o único chamador é `resolveSession`
> (src/auth/session.ts:40), que faz o guard na linha anterior. O review leu a
> assinatura, que é nullable por causa do contrato público, mas este caminho é
> interno e o invariante é garantido pelo chamador.

That costs two minutes and it is the difference between a filter that stays
useful and one that everyone learns to ignore.

### Legitimate reasons for `invalid`

- The triggering input cannot reach the code; name the guard and where it lives.
- The behavior is specified, and the review misread the spec; cite the
  requirement.
- The code was already changed and the finding is stale; say where it went.
- The pattern is an intentional, documented choice; cite the comment or decision
  record.
- The suggested fix would break a contract the review did not read; name the
  contract.

### Not reasons for `invalid`

- The fix is tedious. That is `valid`, and possibly deferred after a user
  decision.
- You disagree with the severity. Severity is not validity; fix it and say the
  severity was high in `Triagem:`.
- It is in code you did not write. Irrelevant.
- The round is large and you want it smaller. That is the exact behavior the
  calibration loop is built to catch.

## Dependencies between findings

Before fixing anything, map which findings share a root cause. The review
deduplicated by root cause, but fixes still interact.

- **Same root cause, separate findings:** fix once, mark both `resolved`, cite
  the same `Fix:`.
- **One fix makes another moot:** mark the second `invalid` with "resolvido pelo
  fix de F<id>" plus why it is no longer reachable.
- **Fixes that conflict:** note it now, decide the order now. Discovering it
  mid-edit costs an attempt from the two-attempt budget.

## Order

Triage in severity order, same as fixing: `critical`, `high`, `medium`, `low`. If
the pass is interrupted, the findings that matter are already decided.

## When triage changes the picture

If triage reveals that a `critical` is actually a `low`, change the severity in
the heading and say why in `Triagem:`. Severity is a review judgment, and triage
is allowed to correct it with evidence.

What triage may **not** do is add a finding. If you find a new problem, it goes
in your report to the user, not in the file.

# fixing.md

# Fixing

Load at Step 2, after every finding is triaged.

## Order

`critical`, then `high`, then `medium`, then `low`. Strictly.

This is not bureaucracy. A remediation pass gets interrupted: context runs out,
the user redirects, a conflict appears. Severity order guarantees that whatever
did land is the part that mattered.

## Scope

The files the findings name. That is the whole scope.

If a fix genuinely requires touching a file no finding names, make the
**minimum** change that works and document why in that finding's `Triagem:`. "The
root cause lives in the shared helper" is a good reason. "While I was there" is
not.

**No refactoring on the side.** No renaming, no reformatting, no tidying adjacent
code, no upgrading a dependency, no improving a test that was not failing. Every
one of those turns a reviewable three-line diff into something nobody can review,
and the user now has to trust you instead of reading.

Cleanup you noticed is a deferred idea in `STATE.md`.

## Root cause, not symptom

The finding cites a location; that is where the problem is **visible**, not
necessarily where it lives.

If a nil dereference appears in a caller because a shared function can return nil
without saying so, the fix is one guard in the shared function, not a patch in
the caller the review happened to look at. Patch the caller and the next caller
hits the same bug, with no finding to catch it.

When the fix lands somewhere other than the cited location, say so in `Triagem:`
and point `Fix:` at where the repair actually lives.

## The laziest fix that works

Climb this ladder, stop at the first rung that holds:

1. A helper or pattern that already exists in this repo
2. The standard library
3. A native platform feature
4. An already-installed dependency
5. One line of new code
6. Minimal new code

Never add a dependency for something three lines cover. Never introduce an
abstraction to fix one finding; a finding is not evidence of a pattern.

## Tests

**Name the invariant that changed and the suite that owns it.** Then:

- **Reuse existing coverage** when a test already pins the behavior. Re-run it;
  if it was passing while the bug existed, the test is the real finding.
- **Add or update a test only for a genuine coverage gap.** One test per
  invariant, not one per finding.
- Test edits needed to validate a fix are in scope. Test edits that make an
  unrelated failure disappear are not.

### The line that must not be crossed

Never weaken a test to make it pass. Not by deleting an assertion, not by
loosening a matcher, not by widening a tolerance, not by adding a skip, not by
catching an exception the test was there to surface.

A test going green because you removed its teeth converts a real finding into a
silent one, and the next review will not catch it because the suite now claims
the behavior is correct. If a test fails after your fix, one of two things is
true: the fix is wrong, or the test was wrong. Decide which, out loud, in
`Triagem:`. Those are the only options.

## When verification fails

In order:

1. **Your fix caused it.** Find the root cause and fix that. Do not revert the
   fix to get green; reverting trades a known defect for a passing suite, which
   is the worst trade available.
2. **Pre-existing and unrelated.** Document it in the relevant `Triagem:` and
   proceed. It is not yours, and silently fixing it widens the diff past what the
   user agreed to review.
3. **Two of your fixes conflict.** Two attempts, maximum. Then document the
   conflict in both findings, set them `blocked`, and report it. Looping on a
   conflict burns the session and produces nothing.

## Findings that share a fix

When one change resolves several findings, mark each `resolved` and point all of
them at the same `Fix:`. Do not write the same repair twice in different places
to make the file look tidier; duplicated fixes drift.

## Findings that cannot be fixed here

- Needs an external change (another service, another repo, a vendor):
  `unresolved`, with the dependency named.
- Needs a decision the user has not made: ask. Asking does not end this step.
  Only if there is nobody to ask does it become `blocked`, with the question
  stated.
- Real but out of appetite: that is the user's call, not yours. Ask. The answer
  is a waiver or a deferral, both recorded.

## Pass-specific notes

**Pass A (contract).** The fix is the missing behavior, not a note in the spec.
If the spec is what is wrong, stop and say so: that is a spec change, it
invalidates tasks, and it does not belong in a review fix.

**Pass B (test parity).** A hollow test gets a real assertion, not a deletion.
The catalog says what the behavior is; make the test say it too.

**Pass E (structure).** The highest-risk fixes in the pass, because they touch
working code. Do the restructuring the finding names, nothing more. If the
restructuring turns out larger than the finding described, stop and report it
rather than reshaping a module nobody asked you to reshape.

**Pass G (bypasses).** A naked suppression gets the underlying problem fixed, or
it gets a justification plus an issue reference. Deleting the suppression and
leaving the lint error is not a fix.

# closeout.md

# Close-out

Load at Step 4. The round file is updated in place; nothing new is created.

## Per finding

| Final status | Required |
| --- | --- |
| `resolved` | `Fix:` pointing at where the repair lives, plus `Triagem:` with the root cause |
| `invalid` | `Triagem:` with concrete reasoning, not a bare dismissal |
| `unresolved` | `Triagem:` naming the external dependency or the deferral entry |
| `blocked` | `Triagem:` naming the blocker |
| `declined-accepted` | `Triagem:` with the author's reason and why it holds |

`pending` and `valid` are **not** terminal. Either one left in the file means the
pass is unfinished.

## The `Fix:` field

```markdown
- **Fix:** `src/billing/invoice.ts:142`
```

A backticked `path:line`, or `path` alone when the repair is not a single line.
Open the file and verify it exists, and that the line is in range.

This is the mirror of the review's verified-citation rule. The review cannot
claim a problem at a location that does not exist; the fix cannot claim a repair
at one either.

When the repair landed somewhere other than the finding's `Local:` (root cause in
a shared function, for example), `Fix:` points at the repair, and `Triagem:`
explains the move.

## Frontmatter

Update two fields:

**`counts`** stays per-severity and must still match the findings. Severity does
not change when a finding is fixed; status does. Only touch `counts` if triage
legitimately corrected a severity.

**`verdict`** is derived from what remains **open**:

| Open findings | Verdict |
| --- | --- |
| any `critical` or `high` still open | `changes-requested` |
| only `medium` or `low` open | `approved-with-followups` |
| nothing open | `approved` |

Open means `pending`, `valid`, `unresolved`, `blocked`, or `declined`. A
`critical` that is `resolved`, `invalid`, or `declined-accepted` is settled and
stops counting.

## What not to touch

- **The index table.** It carries ID, severity, location, and summary. Status is
  not in it, by design: a status column would mean two edits per triage and a
  reconciliation check.
- **IDs.** F1 is F1 forever. This is what makes the next round's Resolução table
  map cleanly.
- **The finding bodies.** The review wrote them. Your reasoning goes in
  `Triagem:`, not by rewriting the claim you are answering.
- **Any other round file.** You are closing one round.

## Adding findings

You do not. If the fix pass surfaces a new problem, it goes in your report to the
user. The round is frozen; that freeze is why the review terminates.

If the new problem is genuinely `critical`, say so in the report and let the user
decide whether it is worth another review run. That decision is theirs, and round
2 has its own rules: at most three new `critical` findings, each naming the fix
that introduced it.

## Promoting findings

Before reporting, look at what was fixed. Anything deterministic by nature (a
banned pattern, a naming rule, something a linter could catch) goes into
`## Promover a convenção` in the round file, then into `STATE.md` as a confirmed
lesson and `CONVENTIONS.md` as a rule.

This is the only step that makes the next review cheaper than this one. A fix
that stays a fix gets rediscovered; a fix that becomes a rule does not.

## The report

State, in this order:

1. What was fixed, by severity.
2. What was dismissed and the strongest reason why, plus the dismissal rate.
3. What remains open, and what it needs (a waiver, a decision, an external
   change).
4. Whether the Merge layer is unblocked, in those words.
5. Anything you noticed that is not in the file, flagged as not a finding.

If `critical` or `high` remain open without a waiver, the Merge layer is not
done. Say it plainly, without softening.

Then stop. No commits, no staging, no suggested commit message. Git is the user's.

# coding-principles.md

# Coding Principles

Behavioral bias, not checklist. Read before every implementation.

---

## Before Coding

- State assumptions explicitly. If uncertain, stop and ask.
- Multiple interpretations exist? Present all—don't pick silently. Never let code
  silently beat an approved spec.
- Spec must change? Say so and stop. Do not rewrite the spec to match the
  implementation.
- Simpler approach exists? Say so. Push back when warranted.
- Something unclear? Stop. Name what's confusing. Ask.
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
- NEVER use the test framework's skip/disable/pending mechanism to bypass a
  failing test
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
