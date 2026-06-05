import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_directory_picker_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_result.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_use_case.dart';

import 'fake_local_directory_picker_service.dart';
import 'fake_recent_projects_repository.dart';

void main() {
  group('ImportLocalProjectUseCase', () {
    late FakeRecentProjectsRepository repository;
    late FakeLocalDirectoryPickerService picker;
    late ImportLocalProjectUseCase useCase;

    setUp(() {
      repository = FakeRecentProjectsRepository();
      picker = FakeLocalDirectoryPickerService();
      useCase = ImportLocalProjectUseCase(
        repository: repository,
        pickerService: picker,
        clock: () => DateTime.utc(2026, 5, 15, 12),
        newProjectId: () => 'uuid-new',
      );
    });

    test(
      'returns cancelled without repository writes when picker cancelled',
      () async {
        picker.nextResult = const DirectoryPickResult(
          DirectoryPickOutcome.cancelled,
        );

        final ImportLocalProjectResult result = await useCase.call();

        expect(result.outcome, ImportLocalProjectOutcome.cancelled);
        expect(repository.upsertCallCount, 0);
        expect(repository.projects, isEmpty);
      },
    );

    test(
      'creates project with UUID, sets active, and persists on successful pick',
      () async {
        picker.nextResult = const DirectoryPickResult(
          DirectoryPickOutcome.success,
          absolutePath: '/Users/dev/team-repo',
        );

        final ImportLocalProjectResult result = await useCase.call();

        expect(result.outcome, ImportLocalProjectOutcome.success);
        expect(result.project?.id, 'uuid-new');
        expect(result.project?.canonicalPath, '/Users/dev/team-repo');
        expect(result.project?.displayName, 'team-repo');
        expect(repository.activeProjectId, 'uuid-new');
        expect(repository.projects, hasLength(1));
      },
    );

    test(
      're-import same canonicalPath returns same UUID without duplicate rows',
      () async {
        picker.nextResult = const DirectoryPickResult(
          DirectoryPickOutcome.success,
          absolutePath: '/Users/dev/team-repo',
        );

        await useCase.call();

        final ImportLocalProjectUseCase reimportUseCase =
            ImportLocalProjectUseCase(
              repository: repository,
              pickerService: picker,
              clock: () => DateTime.utc(2026, 5, 16, 8),
              newProjectId: () => 'uuid-other',
            );

        final ImportLocalProjectResult result = await reimportUseCase.call();

        expect(result.outcome, ImportLocalProjectOutcome.success);
        expect(result.project?.id, 'uuid-new');
        expect(repository.projects, hasLength(1));
        expect(
          repository.projects.single.lastAccessedAt,
          DateTime.utc(2026, 5, 16, 8),
        );
      },
    );

    test('eleventh import drops project with oldest lastAccessedAt', () async {
      for (int index = 0; index < 10; index++) {
        repository.projects.add(
          LocalProjectEntity(
            id: 'uuid-$index',
            canonicalPath: '/Users/dev/project-$index',
            displayName: 'project-$index',
            lastAccessedAt: DateTime.utc(2026, 5, 1, index),
          ),
        );
      }

      picker.nextResult = const DirectoryPickResult(
        DirectoryPickOutcome.success,
        absolutePath: '/Users/dev/project-new',
      );

      final ImportLocalProjectUseCase cappedUseCase = ImportLocalProjectUseCase(
        repository: repository,
        pickerService: picker,
        clock: () => DateTime.utc(2026, 5, 20, 12),
        newProjectId: () => 'uuid-new-project',
      );

      final ImportLocalProjectResult result = await cappedUseCase.call();

      expect(result.outcome, ImportLocalProjectOutcome.success);
      expect(repository.projects, hasLength(10));
      expect(
        repository.projects.any(
          (LocalProjectEntity project) => project.id == 'uuid-0',
        ),
        isFalse,
      );
      expect(
        repository.projects.any(
          (LocalProjectEntity project) => project.id == 'uuid-new-project',
        ),
        isTrue,
      );
      expect(repository.replaceCallCount, greaterThan(0));
    });
  });
}
