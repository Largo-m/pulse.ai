Continue the **{{phase}}** phase based on the user's choice.
Workspace: `{{workspace}}`
Feature: `{{feature_slug}}`
Original task: {{user_prompt}}

## User answer (authoritative)

{{answers}}

## Previous analysis

{{summary}}

{{agent}}

The user answered the clarify. Fold the answers into `PRD.md`, the Ambiguity
Ledger and `context.md`.

Then reassess: is any gray area, doubt or `open` row still left?

- **Something is left** → run the next round of questions and end your reply with
  it. No approval block. There is no cap on rounds.
- **Nothing is left** → present the spec and end with the approval block.

Still forbidden: writing `assumed` in the ledger, presenting with an `open` row,
and using technical vocabulary in the wording of a question (that belongs to Techspec).

Reminder: when you finish, update workflow.yaml and end with the CLI approval block.

{{output_language}}
