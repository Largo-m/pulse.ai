import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';

import 'fake_recent_projects_repository.dart';

void main() {
  group('SelectActiveProjectUseCase', () {
    test('readActiveProjectId returns repository value', () async {
      final FakeRecentProjectsRepository repository =
          FakeRecentProjectsRepository()
            ..activeProjectId = '/Users/dev/team-repo';
      final SelectActiveProjectUseCase useCase = SelectActiveProjectUseCase(
        repository,
      );

      expect(await useCase.readActiveProjectId(), '/Users/dev/team-repo');
    });

    test('persists given project id via repository', () async {
      final FakeRecentProjectsRepository repository =
          FakeRecentProjectsRepository();
      final SelectActiveProjectUseCase useCase = SelectActiveProjectUseCase(
        repository,
      );

      await useCase.select('/Users/dev/team-repo');

      expect(repository.activeProjectId, '/Users/dev/team-repo');
    });

    test(
      'clears active id when it is not present in recent projects',
      () async {
        final FakeRecentProjectsRepository repository =
            FakeRecentProjectsRepository()
              ..activeProjectId = '/Users/dev/missing'
              ..projects.add(
                LocalProjectEntity(
                  id: '/Users/dev/still-here',
                  absolutePath: '/Users/dev/still-here',
                  displayName: 'still-here',
                  lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
                ),
              );

        final SelectActiveProjectUseCase useCase = SelectActiveProjectUseCase(
          repository,
        );

        await useCase.reconcileActiveWithRecentProjects();

        expect(repository.activeProjectId, isNull);
      },
    );
  });
}
