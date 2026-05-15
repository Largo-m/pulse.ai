import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/data/models/recent_projects_document.dart';
import 'package:pulse_ai/features/orchestrator/data/recent_projects_local_storage.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/recent_projects_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  group('RecentProjectsRepositoryImpl', () {
    late RecentProjectsRepositoryImpl repository;

    setUp(() async {
      SharedPreferences.setMockInitialValues(<String, Object>{});
      final SharedPreferences preferences =
          await SharedPreferences.getInstance();
      repository = RecentProjectsRepositoryImpl(
        RecentProjectsLocalStorage(preferences),
      );
    });

    LocalProjectEntity project({
      required String id,
      required DateTime accessedAt,
    }) {
      return LocalProjectEntity(
        id: id,
        absolutePath: id,
        displayName: 'team-repo',
        lastAccessedAt: accessedAt,
      );
    }

    test('listRecent returns empty list when storage key is missing', () async {
      expect(await repository.listRecent(), isEmpty);
      expect(await repository.getActiveProjectId(), isNull);
    });

    test('local storage clear removes persisted document', () async {
      final SharedPreferences preferences =
          await SharedPreferences.getInstance();
      final RecentProjectsLocalStorage storage = RecentProjectsLocalStorage(
        preferences,
      );

      await storage.writeRaw(
        RecentProjectsDocument(
          schemaVersion: RecentProjectsDocument.currentSchemaVersion,
          activeProjectId: '/Users/dev/team-repo',
          projects: <LocalProjectEntity>[
            LocalProjectEntity(
              id: '/Users/dev/team-repo',
              absolutePath: '/Users/dev/team-repo',
              displayName: 'team-repo',
              lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
            ),
          ],
        ).encode(),
      );

      await storage.clear();

      expect(storage.readRaw(), isNull);
    });

    test(
      'upsertAndPromote then listRecent returns projects in stored order',
      () async {
        final DateTime older = DateTime.utc(2026, 5, 14, 12);
        final DateTime newer = DateTime.utc(2026, 5, 15, 12);

        await repository.upsertAndPromote(
          project(id: '/Users/dev/first', accessedAt: older),
        );
        await repository.upsertAndPromote(
          project(id: '/Users/dev/second', accessedAt: newer),
        );

        final List<LocalProjectEntity> recent = await repository.listRecent();

        expect(recent, hasLength(2));
        expect(recent.first.id, '/Users/dev/second');
        expect(recent.last.id, '/Users/dev/first');
      },
    );

    test('setActiveProjectId round-trips through getActiveProjectId', () async {
      await repository.upsertAndPromote(
        project(
          id: '/Users/dev/team-repo',
          accessedAt: DateTime.utc(2026, 5, 15, 12),
        ),
      );

      await repository.setActiveProjectId('/Users/dev/team-repo');

      expect(await repository.getActiveProjectId(), '/Users/dev/team-repo');
    });

    test('malformed JSON returns empty list and null active id', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{
        RecentProjectsLocalStorage.storageKey: '{not-valid-json',
      });
      final SharedPreferences preferences =
          await SharedPreferences.getInstance();
      final RecentProjectsRepositoryImpl corruptRepository =
          RecentProjectsRepositoryImpl(RecentProjectsLocalStorage(preferences));

      expect(await corruptRepository.listRecent(), isEmpty);
      expect(await corruptRepository.getActiveProjectId(), isNull);
    });

    test('corrupt schema JSON returns empty list and null active id', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{
        RecentProjectsLocalStorage.storageKey:
            '{"schemaVersion":"one","projects":[]}',
      });
      final SharedPreferences preferences =
          await SharedPreferences.getInstance();
      final RecentProjectsRepositoryImpl corruptRepository =
          RecentProjectsRepositoryImpl(RecentProjectsLocalStorage(preferences));

      expect(await corruptRepository.listRecent(), isEmpty);
      expect(await corruptRepository.getActiveProjectId(), isNull);
    });

    test(
      're-upsert promotes project to front without duplicate rows',
      () async {
        final DateTime firstAccess = DateTime.utc(2026, 5, 14, 12);
        final DateTime secondAccess = DateTime.utc(2026, 5, 15, 8);
        final DateTime refreshedAccess = DateTime.utc(2026, 5, 15, 18);

        await repository.upsertAndPromote(
          project(id: '/Users/dev/alpha', accessedAt: firstAccess),
        );
        await repository.upsertAndPromote(
          project(id: '/Users/dev/beta', accessedAt: secondAccess),
        );
        await repository.upsertAndPromote(
          project(id: '/Users/dev/alpha', accessedAt: refreshedAccess),
        );

        final List<LocalProjectEntity> recent = await repository.listRecent();

        expect(recent, hasLength(2));
        expect(recent.first.id, '/Users/dev/alpha');
        expect(recent.first.lastAccessedAt, refreshedAccess);
        expect(recent.last.id, '/Users/dev/beta');
      },
    );
  });

  group('RecentProjectsDocument', () {
    test('encode and tryParse round-trip document fields', () {
      final RecentProjectsDocument document = RecentProjectsDocument(
        schemaVersion: RecentProjectsDocument.currentSchemaVersion,
        activeProjectId: '/Users/dev/team-repo',
        projects: <LocalProjectEntity>[
          LocalProjectEntity(
            id: '/Users/dev/team-repo',
            absolutePath: '/Users/dev/team-repo',
            displayName: 'team-repo',
            lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        ],
      );

      final RecentProjectsDocument? parsed = RecentProjectsDocument.tryParse(
        document.encode(),
      );

      expect(parsed, isNotNull);
      expect(parsed!.schemaVersion, 1);
      expect(parsed.activeProjectId, '/Users/dev/team-repo');
      expect(parsed.projects, hasLength(1));
      expect(parsed.projects.first.displayName, 'team-repo');
    });
  });
}
