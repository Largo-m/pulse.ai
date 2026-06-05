import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/data/migration/recent_projects_document_migrator.dart';
import 'package:pulse_ai/features/orchestrator/data/models/recent_projects_document.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';

void main() {
  group('RecentProjectsDocumentMigrator', () {
    late int uuidSequence;
    late RecentProjectsDocumentMigrator migrator;

    setUp(() {
      uuidSequence = 0;
      migrator = RecentProjectsDocumentMigrator(
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

        final RecentProjectsDocument migrated = migrator.migrate(v1);

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

      final RecentProjectsDocument migrated = migrator.migrate(v1);

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

      final RecentProjectsDocument migrated = migrator.migrate(v2);

      expect(identical(migrated, v2), isTrue);
    });
  });
}
