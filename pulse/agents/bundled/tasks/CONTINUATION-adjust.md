Continue the **{{phase}}** phase based on the user's choice.
Workspace: `{{workspace}}`
Feature: `{{feature_slug}}`
Original task: {{user_prompt}}

## User answer (authoritative)

{{answers}}

## Previous analysis

{{summary}}

{{agent}}

The user asked for **adjustments** before approving.
Update the phase artefacts and present the summary again with a new approval block.
Do not advance to the next phase.

Reminder: when you finish, update workflow.yaml and end with the CLI approval block.

{{output_language}}
