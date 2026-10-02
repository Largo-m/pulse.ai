Workspace: `{{workspace}}`
Original task: {{user_prompt}}

<!-- include: isolation -->

<!-- include: handoff -->

## Review fix phase — remediate the round (do NOT review)

{{#if previous_status}}Previous step outcome: `{{previous_status}}`.

{{/if}}### Read this before anything else

`skipped` above means the person saw the review and chose **not** to have it
corrected in this run. That decision is yours to honour, not to revisit: do not
open the round file, do not read the diff, do not change a single line. Close
immediately with `status: done`, saying that the round stays on disk as written
and nobody asked for a repair. Anything else undoes an explicit instruction from
the user.

Anything other than `skipped` means the review was approved and this step runs.

### When it runs

The round file is the entire scope: the highest `round-NNN.md` in
`.pulse/specs/features/<slug>/reviews/`. If there is no such file, the review
found nothing — say so and close `done`. Do not go looking for work.

Only the newest round is yours. Earlier rounds were closed by earlier passes of
this same step, and reopening one would restart the loop this design exists to
terminate.

Follow the `review-fix.md` playbook above, in order:

1. Read the whole round file plus the artefacts the findings cite.
2. Triage **every** finding before editing any line.
3. Fix the `valid` ones in severity order, inside the files the findings name.
4. Verify with the project's own checks.
5. Close the round file in place: terminal status on every finding, `Fix:` on
   every `resolved`, `counts` and `verdict` recomputed.
6. Run the Step 5 self-check, then promote what deserves to become a rule.

Never add a finding and never open a new round — that freeze is what makes the
review terminate. Something new that is genuinely `critical` goes in your closing
report, for the user to decide.

Do not run git operations (no commit, no staging, no suggesting commit messages).

### How this step closes — and whether the review runs again

There is no approval here, so you are the one attesting the delivery. **You also
decide whether the merge layer is finished**, with the `next` field: the run goes
back to the review step when you ask for it, and ends when you do not.

The rule is one line: **changed code means another review.**

````text
```pulse:outcome
status: done
next: repeat
```
````

Use `next: repeat` when you edited **any** file in this pass. Something you just
repaired can break something else, and nobody has looked at the repair yet —
that second look is the whole reason the loop exists. The next review will not
re-review the feature from scratch; it checks your fixes and accepts only what a
fix broke.

Omit `next` when nothing changed: every finding was `invalid`, there was no round
file, or the person skipped the review. There is nothing to look at again.

````text
```pulse:outcome
status: done
```
````

Use `blocked` when a `critical` or `high` is still open and the person has
neither waived nor deferred it, naming what is missing:

````text
```pulse:outcome
status: blocked
needs: user
```
````

Closing `done` with a blocker open would tell the pipeline the merge layer is
finished when it is not — and asking for another round does not fix a blocker,
because the next review cannot decide what only the person can.

The loop has a ceiling of three rounds. At the ceiling the run moves on whatever
you ask, so whatever is still open has to be in your report, not deferred to a
round that will not happen.

<!-- include: output-language -->
