Quick Mode, phase 2 — implement the **approved** quick task.
Workspace: `{{workspace}}`
Task: {{user_prompt}}

{{isolation}}

{{agent}}

## This run's plan (phase 1)

{{summary}}

{{#if answers}}## User approval

Collected in the terminal, authoritative:

{{answers}}

{{/if}}Run steps 3–5 from `quick-mode.md`:

1. Update `.pulse/specs/quick/NNN-slug/TASK.md` → **Status: In Progress**.
2. Implement following `coding-principles.md`: the simplest code that works,
   touch **only** the files listed in TASK.md, no scope creep.
3. Verify per the TASK.md Verification section. Mark it done only after it passes.
4. Update `TASK.md` → **Status: Done** and tick the verification boxes.
5. Write `.pulse/specs/quick/NNN-slug/SUMMARY.md` with what changed and the
   verification result.
6. Update `.pulse/specs/project/STATE.md` → the Quick Tasks row to ✅ Done.

If the scope grows (>3 files, a design decision, a new dependency), **stop** and
record it in TASK.md instead of forcing the implementation through.
Do not run git operations (no commit, no suggesting commit messages).

{{output_language}}
