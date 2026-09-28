Analyze codebase, phase 2 — write the brownfield documentation in `.pulse/specs/codebase/`.
Workspace: `{{workspace}}`
Initial context: {{user_prompt}}

{{isolation}}

{{agent}}

## This run's analysis (phase 1)

{{summary}}

{{#if answers}}## User answers (questionnaire)

These answers were collected in the terminal and are authoritative:

{{answers}}

{{/if}}Write the 7 artefacts per `brownfield-mapping.md`:
{{artifact_list}}

For `CONCERNS.md`, follow the template in `concerns.md`.
Document only what you have concrete evidence for (paths, patterns, commands).
Respect the size limit each file has in `brownfield-mapping.md`.

{{output_language}}
