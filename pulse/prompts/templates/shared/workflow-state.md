## Workflow state (mandatory)

Update `.pulse/specs/features/{{feature_slug}}/workflow.yaml` when this phase ends:

- `feature_slug`: `{{feature_slug}}`
- `complexity`: assess it (small/medium/large/complex)
- `current_phase`: the current phase
- `phases.<phase>.status`: `awaiting_approval` when you finish
- `phases.techspec.skip`: `true` only when Techspec is not needed
- `phases.tasks.skip`: always `false` — the full pipeline always writes `tasks.md`
- `phases.techspec.skip_reason`: the reason when Techspec is skipped

Pulse reads this file to decide the next phase. Keep it consistent.
