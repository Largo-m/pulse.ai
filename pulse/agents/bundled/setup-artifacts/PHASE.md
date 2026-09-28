Setup project, phase 2 — write the artefacts in `.pulse/specs/project/`.
Workspace: `{{workspace}}`
Initial context: {{user_prompt}}

{{isolation}}

{{agent}}

## This run's analysis (phase 1)

{{summary}}

{{#if answers}}## User answers (questionnaire)

These answers were collected in the terminal and are authoritative:

{{answers}}

{{/if}}Treat the answers above as the source of truth. Do not invent what was not answered.

Explore the workspace if you need to, then write:
- `.pulse/specs/project/PROJECT.md` per `project-init.md`.
- `.pulse/specs/project/ROADMAP.md` per `roadmap.md`.
- `.pulse/specs/project/STATE.md` per `state-management.md`.

{{output_language}}
