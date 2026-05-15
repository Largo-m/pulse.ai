import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';

import 'fake_recent_projects_repository.dart';

void main() {
  group('ListRecentProjectsUseCase', () {
    test('returns empty list when store is empty', () async {
      final FakeRecentProjectsRepository repository =
          FakeRecentProjectsRepository();
      final ListRecentProjectsUseCase useCase = ListRecentProjectsUseCase(
        repository,
      );

      expect(await useCase.call(), isEmpty);
    });

    test('returns projects sorted by lastAccessedAt descending', () async {
      final FakeRecentProjectsRepository repository =
          FakeRecentProjectsRepository()
            ..projects.addAll(<LocalProjectEntity>[
              LocalProjectEntity(
                id: '/Users/dev/older',
                absolutePath: '/Users/dev/older',
                displayName: 'older',
                lastAccessedAt: DateTime.utc(2026, 5, 10, 12),
              ),
              LocalProjectEntity(
                id: '/Users/dev/newer',
                absolutePath: '/Users/dev/newer',
                displayName: 'newer',
                lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
              ),
            ]);

      final ListRecentProjectsUseCase useCase = ListRecentProjectsUseCase(
        repository,
      );

      final List<LocalProjectEntity> recent = await useCase.call();

      expect(recent.first.id, '/Users/dev/newer');
      expect(recent.last.id, '/Users/dev/older');
    });
  });
}
