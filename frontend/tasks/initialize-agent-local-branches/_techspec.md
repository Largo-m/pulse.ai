# TechSpec: Local Branch Loading in Initialize Agent Modal

## Executive Summary

Replace hardcoded branch names in `initialize_agent_modal.dart` with real local branches loaded from the selected project's `absolutePath`. The implementation adds a **`LocalGitBranchesService`** (git2dart/libgit2 in `service/`), a **`ListLocalGitBranchesUseCase`**, and an **`InitializeAgentBranchesCubit`** registered in **`OrchestratorComposition`**. The modal triggers loads on open and project change, renders PRD-mandated loading/error/non-Git states, disables **Salvar** until a valid branch is selectable, and returns form data through an optional **`onSubmit`** callback.

**Primary trade-off:** git2dart adds native libgit2 binaries and rebuild cost, but avoids PATH-dependent CLI behavior and keeps Git semantics centralized in one testable service. **Rejected for MVP:** `Process.run('git')` and manual `.git` parsing (see ADR-002).

## System Architecture

### Component Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│ presentation/widgets/initialize_agent_modal.dart                │
│  - showInitializeAgentModal(..., onSubmit?)                     │
│  - BlocBuilder<InitializeAgentBranchesCubit, State>             │
│  - project ValueNotifier → cubit.loadForProject(path)           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ presentation/bloc/initialize_agent_branches_cubit.dart          │
│  - loadForProject(String absolutePath)                          │
│  - selectBranch(String name)                                    │
│  - reset() on modal close                                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ domain/usecases/list_local_git_branches_use_case.dart           │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ domain/service/local_git_branches_service.dart (interface)      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│ service/local_git_branches_service_impl.dart (git2dart)         │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow**

1. Modal opens → resolve `LocalProjectEntity` from `projectId` → `cubit.loadForProject(entity.absolutePath)`.
2. Cubit emits `loading` → use case → service opens repo → returns branch names + head name.
3. Cubit emits `loaded` with branches (libgit2 order), `selectedBranch` = head when it matches a listed local branch.
4. User changes project dropdown → new `loadForProject` (stale responses ignored via load generation).
5. User taps **Salvar** (enabled only in `loaded` with non-null `selectedBranch`) → `onSubmit(InitializeAgentSubmitPayload)` → `Navigator.pop`.

**External systems:** None (local libgit2 only).

## Implementation Design

### Core Interfaces

```dart
// lib/features/orchestrator/domain/service/local_git_branches_service.dart

enum LocalGitBranchesOutcome { success, notGitRepository, failure }

final class LocalGitBranchesResult {
  const LocalGitBranchesResult(
    this.outcome, {
    this.branches = const <String>[],
    this.headBranchName,
    this.debugMessage,
  });

  final LocalGitBranchesOutcome outcome;
  final List<String> branches;
  final String? headBranchName;
  final String? debugMessage;
}

abstract interface class LocalGitBranchesService {
  Future<LocalGitBranchesResult> listLocalBranches(String absolutePath);
}
```

```dart
// lib/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart

final class ListLocalGitBranchesUseCase {
  ListLocalGitBranchesUseCase({required LocalGitBranchesService service})
      : _service = service;

  final LocalGitBranchesService _service;

  Future<LocalGitBranchesResult> call(String absolutePath) {
    return _service.listLocalBranches(absolutePath);
  }
}
```

```dart
// lib/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart

final class InitializeAgentSubmitPayload {
  const InitializeAgentSubmitPayload({
    required this.agentName,
    required this.coreDirective,
    required this.projectId,
    required this.branchName,
  });

  final String agentName;
  final String coreDirective;
  final String projectId;
  final String branchName;
}
```

**Service implementation sketch** (`local_git_branches_service_impl.dart`):

- Injectable `RepositoryOpener` typedef: `Repository Function(String path)` defaulting to `Repository.open`.
- `try { final repo = _open(path); ... } on GitException / ArgumentError → notGitRepository or failure`.
- `branches = repo.branchesLocal.map((b) => b.name).toList()` (confirm `Branch.name` API in implementation).
- `headBranchName` from `repo.head` shorthand when not detached; if `repo.isHeadDetached`, return `headBranchName: null` (branches still listed).
- `finally { repo.free(); }` or package-dispose equivalent per git2dart docs.

### Data Models

**Cubit state** (`initialize_agent_branches_state.dart`):

| Field | Type | Purpose |
|-------|------|---------|
| `status` | `BranchLoadStatus` | `initial`, `loading`, `loaded`, `notGitRepository`, `failure` |
| `branches` | `List<String>` | Dropdown items (libgit2 order) |
| `selectedBranch` | `String?` | User selection; defaulted from HEAD when valid |
| `activePath` | `String?` | Path of in-flight or last successful load (debug/tests) |
| `loadGeneration` | `int` | Stale-response guard |

**Status → UI mapping** (strings from `OrchestratorStrings`, not stored in state):

| Status | Branch dropdown | Helper text |
|--------|-----------------|-------------|
| `loading` | Disabled + `CircularProgressIndicator` | `initializeAgentBranchesLoading` |
| `loaded` | Enabled | Optional metadata-only helper |
| `notGitRepository` | Disabled | `initializeAgentBranchesNotGit` |
| `failure` | Disabled | `initializeAgentBranchesLoadFailed` |
| `initial` | Disabled | None until first load |

**Submit enablement:** `status == loaded && selectedBranch != null && branches.contains(selectedBranch)`.

### API Endpoints

Not applicable (no HTTP).

## Integration Points

| Integration | Role |
|-------------|------|
| **git2dart / libgit2** | Open repo, `branchesLocal`, `head`, `isHeadDetached` |
| **OrchestratorComposition** | Construct service → use case → cubit; register in `MultiBlocProvider` |
| **RecentProjectsCubit** | Unchanged; still supplies `projects` + `activeProjectId` to modal |
| **Agent creation (future)** | Consumes `InitializeAgentSubmitPayload` from `onSubmit` |

**Authentication:** N/A.

**Retry:** User changes project or reopens modal; no automatic retry loop in MVP.

## Impact Analysis

| Component | Impact Type | Description and Risk | Required Action |
|-----------|-------------|---------------------|-----------------|
| `pubspec.yaml` | Modified | Add `git2dart` native dep | Pin version; `flutter pub get` |
| `local_git_branches_service.dart` | New | Domain contract | Unit-test via fake |
| `local_git_branches_service_impl.dart` | New | libgit2 IO | Inject opener for tests |
| `list_local_git_branches_use_case.dart` | New | Thin wrapper | Use case tests |
| `initialize_agent_branches_cubit.dart` | New | Modal state machine | `bloc_test` |
| `initialize_agent_submit_payload.dart` | New | Callback DTO | — |
| `orchestrator_composition.dart` | Modified | Wire cubit | `dispose()` close cubit |
| `initialize_agent_modal.dart` | Modified | Remove `_branchValues`; Bloc + callback | Manual QA |
| `orchestrator_strings.dart` | Modified | PT-BR copy + semantics | Update strings test |
| `orchestrator_page.dart` | Modified | Pass `onSubmit` when wired | Optional stub in MVP |
| `fake_local_git_branches_service.dart` | New (test) | Test double | — |

## Testing Approach

### Unit Tests

| Target | Scenarios |
|--------|-----------|
| `ListLocalGitBranchesUseCase` | Delegates path to service |
| `LocalGitBranchesServiceImpl` | Success with branches + head; not a repo; open throws; detached HEAD (`headBranchName` null, branches non-empty) |
| `InitializeAgentBranchesCubit` | loading→loaded; notGitRepository; failure; `selectBranch`; rapid project switch drops stale emit; `reset()` |
| `OrchestratorStrings` | New keys non-empty |

**Mocks:** `FakeLocalGitBranchesService` in `test/features/orchestrator/domain/usecases/`; inject fake `RepositoryOpener` in service impl test (return mock repo or throw).

**Boundaries:** No git2dart in domain/presentation tests except service impl test (optional: skip impl integration test on CI without native lib — prefer fake opener returning canned data).

### Integration Tests

Not required for MVP. Manual QA matrix per PRD: multi-branch repo, non-Git folder, permission failure simulation, project switch refreshes list and HEAD default.

## Development Sequencing

### Build Order

1. **Add `git2dart` dependency** — no code dependencies.
2. **Domain service interface + `LocalGitBranchesResult`** — depends on step 1 only for eventual impl import path planning (domain stays git-free).
3. **`LocalGitBranchesServiceImpl`** — depends on steps 1–2.
4. **`ListLocalGitBranchesUseCase`** — depends on step 2.
5. **Unit tests: fake service, use case, service impl (injected opener)** — depends on steps 3–4.
6. **`InitializeAgentBranchesState` + Cubit** — depends on step 4.
7. **Cubit unit tests** — depends on step 6.
8. **`OrchestratorComposition` wiring + dispose** — depends on steps 3, 6.
9. **`OrchestratorStrings` + strings test** — no hard dependency; parallelizable after step 6.
10. **`InitializeAgentSubmitPayload` + modal UI** — depends on steps 6, 8, 9.
11. **`showInitializeAgentModal` signature (`onSubmit`) + orchestrator_page caller** — depends on step 10.
12. **`flutter analyze` + `dart format .`** — depends on all above.

### Technical Dependencies

- Developers need successful `flutter pub get` with git2dart native libraries on target desktop OS.
- Confirm `Branch` name accessor and repository dispose API against installed git2dart version during step 3 spike (≤30 min).

## Monitoring and Observability

MVP: no production telemetry. Optional `debugPrint` of `LocalGitBranchesOutcome` behind `kDebugMode` in service impl only. No user-visible `debugMessage`.

## Technical Considerations

### Key Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| git2dart (ADR-002) | Stakeholder choice; accurate Git semantics | Native binary weight |
| Composition-scoped Cubit (ADR-003) | Matches orchestrator DI | Must `reset()` on modal close |
| libgit2 branch order | Stakeholder choice | Less predictable than alphabetical |
| Submit disabled until valid branch | Prevents invalid agent metadata | Blocks save on detached HEAD until user picks |
| `onSubmit` callback (ADR implicit) | Decouples modal from agent persistence | Callers must handle null optional until wired |

### Detached HEAD

When `isHeadDetached == true`, emit `loaded` with `branches` populated but `selectedBranch == null`. Dropdown enabled; user must pick a local branch; **Salvar** stays disabled until selection.

### Rapid project switching

Increment `loadGeneration` on each `loadForProject`. Before emit after await, if generation changed, return without emitting.

### Known Risks

| Risk | Mitigation |
|------|------------|
| git2dart platform build failure | Verify on macOS first; document Windows/Linux setup in task notes |
| Large branch lists slow UI | PRD Phase 2 search; MVP acceptable |
| Repository handle leak | `try/finally` dispose in service |
| Modal shows stale cubit state | `reset()` in modal `dispose` and when dialog completes |

## Architecture Decision Records

- [ADR-001: Reactive Local Branch Loading per Project](adrs/adr-001.md) — Product: reactive load, local branches only, HEAD default, metadata-only.
- [ADR-002: git2dart (libgit2) for Local Branch Enumeration](adrs/adr-002.md) — Use git2dart in service layer; reject CLI and manual `.git` parsing.
- [ADR-003: InitializeAgentBranchesCubit in OrchestratorComposition](adrs/adr-003.md) — App-scoped cubit via composition; reject ephemeral/local ValueNotifier state machine.
