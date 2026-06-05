# TechSpec: Local Project Import and Recent Projects Sidebar

## Executive Summary

This MVP adds local folder import, a contextual recent-projects sidebar with active selection, and session persistence on desktop. Implementation extends the existing orchestrator presentation layer with new **domain**, **data**, and **service** layers under `lib/features/orchestrator/`, introduces **`RecentProjectsCubit`** and **`ImportFlowCubit`**, and renames **`OrchestratorEmptyPage`** to **`OrchestratorPage`** on the unchanged `RoutePaths.orchestrator` route.

Persistence uses a versioned JSON document in **`shared_preferences`** (list ≤10 + `activeProjectId`). Project identity is the **normalized absolute path**. Import uses **`file_picker`** behind `LocalDirectoryPickerService`; `ImportFlowCubit` runs the use case, and the import page performs **`popUntil`** plus **`RecentProjectsCubit.refresh()`** on success.

**Primary trade-off:** `shared_preferences` and split cubits minimize infrastructure and keep import isolated, at the cost of the **page orchestrating navigation and list refresh** after import rather than a single facade cubit.

## System Architecture

### Component Overview

```text
┌─────────────────────────────────────────────────────────────────┐
│ Presentation                                                     │
│  OrchestratorPage ── RecentProjectsCubit (list, active)         │
│  ImportProjectSelectSourcePage ── ImportFlowCubit (picker flow) │
│  RecentProjectsSidebar / RecentProjectListTile                  │
└────────────┬───────────────────────────────┬────────────────────┘
             │                               │
             ▼                               ▼
┌────────────────────────┐    ┌──────────────────────────────────┐
│ Domain                  │    │ Service                           │
│  LocalProjectEntity     │    │  LocalDirectoryPickerService      │
│  RecentProjectsRepository│   │  (file_picker wrapper)            │
│  Use cases              │    └──────────────────────────────────┘
└────────────┬───────────┘
             ▼
┌────────────────────────┐
│ Data                    │
│  RecentProjectsRepositoryImpl
│  RecentProjectsLocalStorage (shared_preferences + JSON)
└────────────────────────┘
```

| Component | Responsibility |
|-----------|----------------|
| `OrchestratorPage` | Conditional `Row`: sidebar when `projects.isNotEmpty`; existing empty/welcome body unchanged |
| `RecentProjectsCubit` | Hydrate on init, expose list + `activeProjectId`, `selectProject`, `refresh` |
| `ImportFlowCubit` | Trigger import, emit loading/success/failure/cancel states |
| `ImportLocalProjectUseCase` | Normalize path, dedupe, cap 10, set active, persist |
| `ListRecentProjectsUseCase` | Read ordered list from repository |
| `SelectActiveProjectUseCase` | Update active id in storage |
| `LocalDirectoryPickerService` | Native directory picker; cancel vs path vs error |
| `RecentProjectsRepositoryImpl` | CRUD on persisted document |

**Data flow — import success:**

1. User taps **Select local** → `ImportFlowCubit.importLocal()` → `ImportLocalProjectUseCase`.
2. Use case calls picker → on path, upserts project, sets active, saves prefs.
3. `ImportFlowCubit` emits success → page `popUntil(RoutePaths.orchestrator)` → `RecentProjectsCubit.refresh()`.

**Data flow — switch active:**

1. User clicks sidebar row → `RecentProjectsCubit.selectProject(id)` → `SelectActiveProjectUseCase` → prefs.

**External systems:** OS folder picker only; no network.

## Implementation Design

### Core Interfaces

```dart
// lib/features/orchestrator/domain/repositories/recent_projects_repository.dart
abstract interface class RecentProjectsRepository {
  Future<List<LocalProjectEntity>> listRecent();

  Future<String?> getActiveProjectId();

  Future<void> upsertAndPromote(LocalProjectEntity project);

  Future<void> setActiveProjectId(String? projectId);
}
```

```dart
// lib/features/orchestrator/domain/service/local_directory_picker_service.dart
enum DirectoryPickOutcome { cancelled, success, failure }

final class DirectoryPickResult {
  const DirectoryPickResult(this.outcome, {this.absolutePath, this.failureMessage});
  final DirectoryPickOutcome outcome;
  final String? absolutePath;
  final String? failureMessage;
}

abstract interface class LocalDirectoryPickerService {
  Future<DirectoryPickResult> pickDirectory();
}
```

```dart
// lib/features/orchestrator/domain/entities/local_project_entity.dart
final class LocalProjectEntity {
  const LocalProjectEntity({
    required this.id,
    required this.absolutePath,
    required this.displayName,
    required this.lastAccessedAt,
  });

  final String id;
  final String absolutePath;
  final String displayName;
  final DateTime lastAccessedAt;
}
```

### Data Models

**Persisted JSON** (`shared_preferences` key `orchestrator.recent_projects.v1`):

```json
{
  "schemaVersion": 1,
  "activeProjectId": "/Users/dev/team-repo",
  "projects": [
    {
      "id": "/Users/dev/team-repo",
      "absolutePath": "/Users/dev/team-repo",
      "displayName": "team-repo",
      "lastAccessedAtIso": "2026-05-15T12:00:00.000Z"
    }
  ]
}
```

| Field | Type | Notes |
|-------|------|-------|
| `id` | `String` | Normalized absolute path |
| `absolutePath` | `String` | For future agent file access |
| `displayName` | `String` | `basename` at import |
| `lastAccessedAtIso` | `String` | ISO-8601; sort descending for sidebar |

**Domain rules (use cases, not entity):**

- Max 10 projects after upsert; drop oldest by `lastAccessedAt`.
- Re-import same `id`: update timestamp, promote to top, no duplicate row.
- On hydrate: if `activeProjectId` not in list, clear active highlight until user selects.

### API Endpoints

Not applicable — local desktop feature only.

## Integration Points

| Integration | Approach |
|-------------|----------|
| `file_picker` | `FilePicker.platform.getDirectoryPath()`; directories only; `lockParentWindow: true` on desktop |
| `shared_preferences` | Single string value; parse failures → empty list + null active |
| `path` | `basename` for display name; `normalize` / absolute resolution in use case |

**Cancel:** picker returns null → `DirectoryPickOutcome.cancelled` → no SnackBar, no persistence.

**Failure:** permissions or platform error → PT-BR message via `OrchestratorStrings` / `ImportProjectStrings`; SnackBar or inline error per existing feedback patterns.

## Impact Analysis

| Component | Impact Type | Description and Risk | Required Action |
|-----------|-------------|---------------------|-----------------|
| `OrchestratorEmptyPage` | Modified | Renamed/replaced by `OrchestratorPage` with sidebar | Rename file, update router test |
| `ShellNavigatorRoutes` | Modified | Builder returns `OrchestratorPage` | Update import |
| `ImportProjectSelectSourcePage` | Modified | Wire local card to `ImportFlowCubit` | Replace `onPlaceholder` for local only |
| `ImportProjectSelectSourceBody` | Modified | Accept `onSelectLocal` callback | Pass from page |
| `OrchestratorStrings` | Modified | Sidebar title, errors, tooltips | Add constants + string tests |
| `PulseDimensions` | Modified | Sidebar width token | Define before UI |
| `pubspec.yaml` | Modified | Add `shared_preferences`, `bloc_test` | `flutter pub get` |
| `lib/features/orchestrator/domain/` | New | Entities, repo, use cases | Create layer |
| `lib/features/orchestrator/data/` | New | Storage adapter, repo impl | Create layer |
| `lib/features/orchestrator/service/` | New | Picker service impl | Create layer |
| `lib/features/orchestrator/presentation/bloc/` | New | Two cubits | Create + tests |
| Remote import card | Unchanged | Still coming soon | Keep placeholder |

## Testing Approach

### Unit Tests

| Area | Focus |
|------|--------|
| `ImportLocalProjectUseCase` | Dedupe, cap 10, promote on re-import, active set, path normalization |
| `SelectActiveProjectUseCase` | Persists active id; clears when invalid |
| `ListRecentProjectsUseCase` | Sort order, empty store |
| `RecentProjectsRepositoryImpl` | Round-trip JSON; corrupt JSON → empty |
| `RecentProjectsCubit` | Hydrate, select, refresh after fake repo update |
| `ImportFlowCubit` | Success, cancel, failure emissions |
| `ProjectPathNormalizer` | If extracted — edge paths |
| Strings | Existing pattern — new keys non-empty PT-BR |

Use fakes for `RecentProjectsRepository` and `LocalDirectoryPickerService`. Add **`bloc_test`** for cubits.

### Integration Tests

Not required for MVP. Manual QA matrix: macOS, Windows, Linux — import, cancel, duplicate path, restart persistence, active restore.

## Development Sequencing

### Build Order

1. **Dependencies** — add `shared_preferences` and `bloc_test`; run `flutter pub get`. No downstream code dependency.
2. **Domain entity + repository interface + path normalizer** — depends on step 1 only for pub resolution.
3. **`RecentProjectsLocalStorage` + `RecentProjectsRepositoryImpl`** — depends on step 2.
4. **Domain use cases** (`ListRecentProjects`, `SelectActiveProject`, `ImportLocalProject`) — depends on steps 2–3.
5. **`LocalDirectoryPickerService` implementation** — depends on step 1 (`file_picker` already present).
6. **Unit tests for steps 3–5** — depends on steps 3–5.
7. **`RecentProjectsCubit` + tests** — depends on steps 4 and 6 patterns.
8. **`ImportFlowCubit` + tests** — depends on steps 4–5.
9. **Composition wiring** in `main.dart` (or minimal DI) — providers for repository, services, use cases, cubits — depends on steps 7–8.
10. **`OrchestratorPage` + `RecentProjectsSidebar` + list tile + DS tokens** — depends on step 7 and 9.
11. **Rename route page + update `shell_navigator_routes_test`** — depends on step 10.
12. **Wire `ImportProjectSelectSourcePage` to `ImportFlowCubit` + navigation refresh** — depends on steps 8–9 and 11.
13. **Strings + string tests** — depends on steps 10–12 (can parallelize copy earlier).
14. **`flutter analyze` + `dart format .` + full unit test run** — depends on all above.

### Technical Dependencies

- `file_picker` ^11 (already in pubspec).
- `shared_preferences` (new).
- No backend or GoRouter requirement for MVP.

## Monitoring and Observability

MVP: no analytics SDK wired. Optional debug logs in repository on parse failure (developer builds only).

**Future (PRD metrics):** funnel events `picker_opened`, `project_saved`, `active_changed` — out of scope for this TechSpec implementation.

## Technical Considerations

### Key Decisions

| Decision | Rationale | Trade-off |
|----------|-----------|-----------|
| `shared_preferences` | Team choice; trivial API for ≤10 items | Whole-document rewrite |
| Split cubits | Isolated import state | Page coordinates pop + refresh |
| Path as `id` | Simple dedupe; agent-ready path | No move/rename handling in MVP |
| `OrchestratorPage` rename | Accurate naming with sidebar | Small churn in router test |
| No new routes for picker | Picker is modal | Import page stays on stack until pop |

### Known Risks

| Risk | Mitigation |
|------|------------|
| Path normalization differs by OS | Unit tests with platform-specific cases where feasible |
| Corrupt prefs JSON | Version key + default empty; repository test |
| User expects project click to open repo | PT-BR copy; no loading faux state |
| Missing folder on disk | MVP silent; Phase 2 warning |
| Forgotten `refresh` after import | Single success listener in import page; cubit test |

### PRD Mapping

| PRD item | Technical component |
|----------|-------------------|
| F1 Local folder import | `ImportLocalProjectUseCase`, `ImportFlowCubit`, picker service |
| F2 Recent sidebar | `RecentProjectsSidebar`, `RecentProjectsCubit`, `OrchestratorPage` layout |
| F3 Session persistence | `RecentProjectsRepositoryImpl`, prefs JSON |
| Empty state unchanged | Sidebar hidden when `projects.isEmpty` |
| Dual import entry points | Top bar route + local card both call same cubit/use case |
| Accessibility active state | `RecentProjectListTile`: border/weight + color (token-based) |

### Open Questions (from PRD — resolved for implementation)

| Question | Resolution |
|----------|------------|
| Active visual treatment | Use DS tokens: left border or font weight + `PulseColors.primary` accent; confirm in UI review |
| Missing folder on select | MVP: allow selection, no warning |
| Skip source selection when experienced | Deferred — keep both entry points through select-source |

## Architecture Decision Records

- [ADR-001: Contextual Recent Projects Sidebar with Active Selection](adrs/adr-001.md) — Sidebar hidden at zero projects; cap 10; active highlight; dedupe on re-import.
- [ADR-002: shared_preferences for Recent Projects Persistence](adrs/adr-002.md) — Versioned JSON document for list and active project id.
- [ADR-003: Split Cubits for Recent Projects and Import Flow](adrs/adr-003.md) — `RecentProjectsCubit` + `ImportFlowCubit`; page handles navigation and refresh.
- [ADR-004: Normalized Absolute Path as Project Identity](adrs/adr-004.md) — Path-based id for dedupe and future agent binding.
- [ADR-005: OrchestratorPage on Existing Orchestrator Route](adrs/adr-005.md) — Rename page; same `RoutePaths.orchestrator`; conditional `Row` layout.
