---
status: completed
title: Dependencies and Hive bootstrap
type: infra
complexity: low
dependencies: []
---

# Task 01: Dependencies and Hive bootstrap

**Phase:** PR-1 — Fundação e identidade de projeto

## Overview

Adiciona as dependências de persistência indexada (`hive`, `hive_flutter`, `fpdart`) e inicializa o Hive no composition root do orchestrator. Esta task desbloqueia repositórios Hive e use cases com `Either<Failure, T>` sem alterar fluxos de UI existentes.

<critical>
- ALWAYS READ the PRD and TechSpec before starting
- REFERENCE TECHSPEC for implementation details — do not duplicate here
- FOCUS ON "WHAT" — describe what needs to be accomplished, not how
- MINIMIZE CODE — show code only to illustrate current structure or problem areas
- TESTS REQUIRED — every task MUST include tests in deliverables
</critical>

<requirements>
- MUST add `hive`, `hive_flutter`, and `fpdart` to `pubspec.yaml` and run `flutter pub get`
- MUST initialize Hive before any box access in `OrchestratorComposition.create()` (or dedicated bootstrap invoked from it)
- MUST register Hive in `lib/app/di/orchestrator_composition.dart` without wiring workflow boxes yet (boxes belong to task_04)
- MUST NOT import Hive or `fpdart` in `domain/` entities from this task alone
- MUST run `dart format .` and `flutter analyze` on touched files before completion
- SHOULD keep `main.dart` changes minimal; prefer composition-root init per TechSpec "Development Sequencing" step 1
</requirements>

## Subtasks
- [x] 1.1 Add packages and refresh lockfile
- [x] 1.2 Implement Hive init helper or inline bootstrap callable from composition
- [x] 1.3 Wire init into `OrchestratorComposition.create()` with safe re-entry on hot restart
- [x] 1.4 Add unit test proving double-init does not throw
- [x] 1.5 Verify existing orchestrator tests still pass

## Implementation Details

See TechSpec sections **Development Sequencing → Build Order (step 1)** and **Technical Dependencies**.

Extend `lib/app/di/orchestrator_composition.dart` following the existing `SharedPreferences` → repository → cubit factory pattern. No new feature routes.

### Relevant Files
- `pubspec.yaml` — new dependencies
- `lib/app/di/orchestrator_composition.dart` — Hive init hook
- `lib/main.dart` — only if init cannot live solely in composition

### Dependent Files
- `pubspec.lock` — updated after `flutter pub get`

## Deliverables
- Updated `pubspec.yaml` with `hive`, `hive_flutter`, `fpdart`
- Hive bootstrap callable from orchestrator composition
- Unit test for init idempotency
- Unit tests with **≥80% coverage** on new bootstrap code **(REQUIRED)**

## Tests
- Unit tests:
  - [x] Hive bootstrap: first call completes without error
  - [x] Hive bootstrap: second call in same process does not throw or corrupt state
  - [x] `flutter analyze` passes on modified paths
- Integration tests:
  - [x] N/A — no boxes or UI in this task
- Test coverage target: >=80%
- All tests must pass

## Success Criteria
- All tests passing
- Test coverage >=80% on new code
- `flutter analyze` passes
- Hive ready for adapter registration in task_04
