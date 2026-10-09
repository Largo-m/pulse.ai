Workspace: `{{workspace}}`
User task: {{user_prompt}}

<!-- include: isolation -->

## PRD phase — capture WHAT to build (do NOT implement)

Follow the `prd.md` playbook above (auto-sizing by complexity).
ACP already loads the workspace rules/skills; do not re-read the whole set by habit.

1. Pick a short kebab-case **feature slug** from the task and create
   `.pulse/specs/features/<slug>/`.
2. Make sure `.pulse/specs/project/STATE.md` exists.
3. Write `.pulse/specs/features/<slug>/PRD.md` with traceable requirements.
4. Every gray area becomes an Ambiguity Ledger row and leaves this phase as
   `decided` (the product team chose) or `n/a` (does not apply to this feature).
   Record the decisions in `context.md`, next to the PRD, per `discuss.md`.
5. Update `STATE.md` → Current Work with this feature.

Open your summary with the **feature slug and its full path**. The next steps run
in a fresh session and find the feature by that path — a summary without it costs
them a search.

Then present: the problem, the scope, the complexity, and whether a Techspec is
needed at all (say so explicitly if it is not).

<!-- include: clarify -->

<!-- include: approval -->

<!-- include: output-language -->
