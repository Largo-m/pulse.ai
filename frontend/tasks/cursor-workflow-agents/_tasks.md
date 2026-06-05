# Cursor PRD Specialist Agent — Task List

## Phases (PRs)

| Fase | Nome | Tarefas | Merge após |
|------|------|---------|------------|
| PR-1 | Fundação e identidade de projeto | 01, 02 | — |
| PR-2 | Persistência Pulse (FS + Hive + UCs base) | 03, 04, 05 | PR-1 |
| PR-3 | Cursor: conexão e serviço híbrido | 06, 07 | PR-2 |
| PR-4 | Lifecycle da run e gates de aprovação | 08, 09 | PR-3 |
| PR-5 | Workspace PRD (UI) | 10, 11, 12 | PR-4 |
| PR-6 | Integração no shell orchestrator | 13 | PR-5 |

## Tasks

| # | Title | Phase | Status | Complexity | Dependencies |
|---|-------|-------|--------|------------|--------------|
| 01 | Dependencies and Hive bootstrap | PR-1 | completed | low | — |
| 02 | Recent projects v2 UUID migration | PR-1 | completed | medium | task_01 |
| 03 | Filesystem artifact store and ArtifactRepository | PR-2 | completed | medium | task_02 |
| 04 | Hive entities, adapters, and workflow/run repositories | PR-2 | completed | high | task_01, task_03 |
| 05 | Workflow and artifact domain use cases | PR-2 | completed | medium | task_04 |
| 06 | Cursor connection port and preflight cubit | PR-3 | completed | medium | task_01 |
| 07 | CursorPrdAgentService hybrid implementation | PR-3 | completed | high | task_02, task_05, task_06 |
| 08 | PRD run lifecycle use cases | PR-4 | completed | high | task_07 |
| 09 | Approve, reject with feedback, and auto-rerun | PR-4 | completed | medium | task_08 |
| 10 | PrdWorkflowCubit and live stream panel | PR-5 | pending | medium | task_08, task_09 |
| 11 | PrdReviewCubit, inline editor, and review actions | PR-5 | completed | medium | task_05, task_09, task_10 |
| 12 | WorkflowPrdWorkspace and connection banner | PR-5 | completed | medium | task_06, task_10, task_11 |
| 13 | Orchestrator shell wiring (slug, submit, sidebar, TechSpec gate) | PR-6 | completed | medium | task_12 |
