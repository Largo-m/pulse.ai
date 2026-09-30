Setup project, phase 2 — write the artefacts in `.pulse/specs/project/`.
Workspace: `{{workspace}}`
Initial context: {{user_prompt}}

<!-- include: isolation-reuse -->

## This run's analysis (phase 1)

{{previous_summary}}

Treat the analysis above as the source of truth — it already carries the user's
answers. Do not invent what was not answered.

Explore the workspace if you need to, then write:
- `.pulse/specs/project/PROJECT.md` per the `project-init.md` playbook above.
- `.pulse/specs/project/ROADMAP.md` per `roadmap.md`.
- `.pulse/specs/project/STATE.md` per `state-management.md`.

<!-- include: output-language -->
