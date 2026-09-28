Continue Quick Mode based on the user's choice in the terminal.
Workspace: `{{workspace}}`
Original task: {{user_prompt}}

## User answer (authoritative)

{{answers}}

## Previous analysis

{{summary}}

{{agent}}

The user chose a **narrowed-scope quick fix** (the predefined option above).
Use that option as the task's new scope.
Re-run the Quick Mode eligibility check against that specific scope.
If it passes: write `.pulse/specs/quick/NNN-slug/TASK.md` (Awaiting Approval),
update STATE.md, present the summary and end with the CLI approval block.
If it still exceeds: explain why and present a new migration block with predefined
options (no free-text "descreva", no "Outro").
Do not implement application code without approval.

{{output_language}}
