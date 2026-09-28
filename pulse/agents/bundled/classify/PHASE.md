Workspace: `{{workspace}}`
User spec: {{user_prompt}}

{{isolation}}

{{agent}}

## Classify phase — pick the flow (do NOT implement)

You are connected to the **Pulse** client.
Classify the user's request into **one** flow:

- `quick` — Small: one sentence, ≤3 files, bug/config/tweak, no design decision, no new dependency
- `full` — Medium/Large/Complex: a feature, several stories, design, ambiguity, or any Quick mode disqualifier

Use the skill's auto-sizing table and **Scope Eligibility** from `quick-mode.md`.
Search the codebase only as much as you need to estimate files and scope.

**Do not** implement application code.
**Do not** create `PRD.md`, `TASK.md`, `TECHSPEC.md` or `tasks.md`.
**Do not** ask the user. Decide.

Write exactly this file: `{{route_path}}`

YAML content (no fence, no extra text in the file). `reason` is written in
Portuguese, because the user reads it:

```yaml
flow: quick
reason: Uma frase objetiva com o motivo
```

`flow` must be `quick` or `full`.
Once the file is written, stop.
