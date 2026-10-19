Workspace: `{{workspace}}`
Original task: {{user_prompt}}

<!-- include: isolation -->

<!-- include: handoff -->

## Verify phase — validate the implementation against the spec (do NOT implement)

Every task in `tasks.md` has been through the implement step. Your job is the
feature layer: prove, with evidence, whether what was built is what the feature's
`PRD.md` and its `TECHSPEC.md` (if it exists) specified.

You did not write this code and you have no notes from whoever did: the summary
above is a claim to check, not evidence. Re-derive the contract from the
artefacts and the code.

### Scope

1. Read `PRD.md`, `TECHSPEC.md` if it exists, and `tasks.md`.
2. `git diff` against the branch this run started from. Read-only — no commit,
   no stage, no push, no stash, no suggesting commit messages.
3. If there is no usable base (shallow clone, detached state, no commits yet),
   fall back to the file list above and say so in `validation.md`.

### What to do

Run the `validate.md` playbook above:

- every acceptance criterion and edge case from `PRD.md`, and every decision
  from `TECHSPEC.md`, gets a `file:line` of evidence or is a gap;
- run the build-level gate;
- run the discrimination sensor **only** in a scratch worktree you discard
  afterwards, and confirm `git status --porcelain` matches the baseline;
- write `.pulse/specs/features/<slug>/validation.md` and update the requirement
  traceability in `PRD.md`.

Do not touch application code or tests in this phase. A gap becomes a fix task
in `validation.md`; repairing it belongs to the steps after this one.

### What to present

Your reply has to stand on its own, because the person decides from it without
opening `validation.md`. Close with:

- the verdict (`PASS` or `FAIL`), first;
- AC coverage (`N/N`) and spec-precision gaps;
- the sensor result (killed, survived, or fallback with the reason);
- the path of `validation.md`;
- every gap, one line each, most severe first: what is missing and where.

<!-- include: approval -->

<!-- include: output-language -->
