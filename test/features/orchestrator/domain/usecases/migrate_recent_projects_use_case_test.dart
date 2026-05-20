import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/data/models/recent_projects_document.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/migrate_recent_projects_use_case.dart';

void main() {
  group('MigrateRecentProjectsUseCase', () {
    late int uuidSequence;
    late MigrateRecentProjectsUseCase useCase;

    setUp(() {
      uuidSequence = 0;
      useCase = MigrateRecentProjectsUseCase(
        newProjectId: () {
          uuidSequence++;
          return 'uuid-$uuidSequence';
        },
      );
    });

    LocalProjectEntity legacyProject({
      required String pathId,
      required DateTime accessedAt,
    }) {
      return LocalProjectEntity(
        id: pathId,
        canonicalPath: pathId,
        displayName: 'repo',
        lastAccessedAt: accessedAt,
      );
    }

    test(
      'v1 document with two path ids produces distinct UUIDs and canonicalPath',
      () {
        final RecentProjectsDocument v1 = RecentProjectsDocument(
          schemaVersion: RecentProjectsDocument.legacySchemaVersion,
          projects: <LocalProjectEntity>[
            legacyProject(
              pathId: '/Users/dev/first',
              accessedAt: DateTime.utc(2026, 5, 14, 12),
            ),
            legacyProject(
              pathId: '/Users/dev/second',
              accessedAt: DateTime.utc(2026, 5, 15, 12),
            ),
          ],
        );

        final RecentProjectsDocument migrated = useCase.call(v1);

        expect(
          migrated.schemaVersion,
          RecentProjectsDocument.currentSchemaVersion,
        );
        expect(migrated.projects, hasLength(2));
        expect(migrated.projects.map((LocalProjectEntity p) => p.id), <String>[
          'uuid-1',
          'uuid-2',
        ]);
        expect(
          migrated.projects.map((LocalProjectEntity p) => p.canonicalPath),
          <String>['/Users/dev/first', '/Users/dev/second'],
        );
      },
    );

    test('rewrites activeProjectId from legacy path id to UUID', () {
      final RecentProjectsDocument v1 = RecentProjectsDocument(
        schemaVersion: RecentProjectsDocument.legacySchemaVersion,
        activeProjectId: '/Users/dev/first',
        projects: <LocalProjectEntity>[
          legacyProject(
            pathId: '/Users/dev/first',
            accessedAt: DateTime.utc(2026, 5, 14, 12),
          ),
          legacyProject(
            pathId: '/Users/dev/second',
            accessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        ],
      );

      final RecentProjectsDocument migrated = useCase.call(v1);

      expect(migrated.activeProjectId, 'uuid-1');
    });

    test('already v2 document is no-op', () {
      final RecentProjectsDocument v2 = RecentProjectsDocument(
        schemaVersion: RecentProjectsDocument.currentSchemaVersion,
        activeProjectId: 'uuid-existing',
        projects: <LocalProjectEntity>[
          LocalProjectEntity(
            id: 'uuid-existing',
            canonicalPath: '/Users/dev/team-repo',
            displayName: 'team-repo',
            lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        ],
      );

      final RecentProjectsDocument migrated = useCase.call(v2);

      expect(identical(migrated, v2), isTrue);
    });
  });
}
