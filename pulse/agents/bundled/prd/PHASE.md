Workspace: `{{workspace}}`
Feature slug: `{{feature_slug}}`
Feature directory: `{{feature_dir}}`
User task: {{user_prompt}}

{{isolation}}

{{agent}}

{{workflow_state}}

## PRD phase — capture WHAT to build (do NOT implement)

Follow `prd.md` and `SKILL.md` (auto-sizing by complexity).
ACP already loads the workspace rules/skills; do not re-read the whole set by habit.

1. Make sure `.pulse/specs/project/STATE.md` exists.
2. Write `{{feature_dir}}/PRD.md` with traceable requirements.
3. Every gray area becomes an Ambiguity Ledger row and leaves this phase as
   `decided` (the product team chose) or `n/a` (does not apply to this feature).
   Record the decisions in `{{feature_dir}}/context.md`, per `discuss.md`.
4. Update `{{workflow_path}}`:
   - Set `complexity`
   - Mark `phases.prd.status: awaiting_approval`
   - If Techspec is not needed: `phases.techspec.skip: true` + `skip_reason`
   - Keep `phases.tasks.skip: false`. Tasks is mandatory in this pipeline.
5. Update `STATE.md` → Current Work with this feature.
6. Run `python3 <skill-dir>/scripts/validate_prd.py <feature>`. A non-zero exit
   means you are still in the clarify loop: ask, do not present.

Present a short summary: problem, scope, complexity, phases that will be skipped.

{{clarify}}

{{approval}}

{{output_language}}
