Analyze codebase, phase 2 — write the brownfield documentation in
`.pulse/specs/codebase/`.
Workspace: `{{workspace}}`
Initial context: {{user_prompt}}

<!-- include: isolation-reuse -->

## This run's analysis (phase 1)

{{previous_summary}}

Write the 7 artefacts per the `brownfield-mapping.md` playbook above:

- `.pulse/specs/codebase/STACK.md`
- `.pulse/specs/codebase/ARCHITECTURE.md`
- `.pulse/specs/codebase/CONVENTIONS.md`
- `.pulse/specs/codebase/STRUCTURE.md`
- `.pulse/specs/codebase/TESTING.md`
- `.pulse/specs/codebase/INTEGRATIONS.md`
- `.pulse/specs/codebase/CONCERNS.md`

For `CONCERNS.md`, follow the template in `concerns.md`.
Document only what you have concrete evidence for (paths, patterns, commands) —
re-read the code when the analysis above is thin, and never fill a gap by guessing.
Respect the size limit each file has in `brownfield-mapping.md`.

<!-- include: output-language -->
