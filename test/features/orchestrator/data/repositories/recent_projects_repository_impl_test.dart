import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/data/models/recent_projects_document.dart';
import 'package:pulse_ai/features/orchestrator/data/recent_projects_local_storage.dart';
import 'package:pulse_ai/features/orchestrator/data/repositories/recent_projects_repository_impl.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/migrate_recent_projects_use_case.dart';
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
        migrateRecentProjectsUseCase: MigrateRecentProjectsUseCase(
          newProjectId: () => 'migrated-uuid',
        ),
      );
    });

    LocalProjectEntity project({
      required String id,
      required String canonicalPath,
      required DateTime accessedAt,
    }) {
      return LocalProjectEntity(
        id: id,
        canonicalPath: canonicalPath,
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
          activeProjectId: 'uuid-1',
          projects: <LocalProjectEntity>[
            LocalProjectEntity(
              id: 'uuid-1',
              canonicalPath: '/Users/dev/team-repo',
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
          project(
            id: 'uuid-first',
            canonicalPath: '/Users/dev/first',
            accessedAt: older,
          ),
        );
        await repository.upsertAndPromote(
          project(
            id: 'uuid-second',
            canonicalPath: '/Users/dev/second',
            accessedAt: newer,
          ),
        );

        final List<LocalProjectEntity> recent = await repository.listRecent();

        expect(recent, hasLength(2));
        expect(recent.first.id, 'uuid-second');
        expect(recent.last.id, 'uuid-first');
      },
    );

    test('setActiveProjectId round-trips through getActiveProjectId', () async {
      await repository.upsertAndPromote(
        project(
          id: 'uuid-team',
          canonicalPath: '/Users/dev/team-repo',
          accessedAt: DateTime.utc(2026, 5, 15, 12),
        ),
      );

      await repository.setActiveProjectId('uuid-team');

      expect(await repository.getActiveProjectId(), 'uuid-team');
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
          project(
            id: 'uuid-alpha',
            canonicalPath: '/Users/dev/alpha',
            accessedAt: firstAccess,
          ),
        );
        await repository.upsertAndPromote(
          project(
            id: 'uuid-beta',
            canonicalPath: '/Users/dev/beta',
            accessedAt: secondAccess,
          ),
        );
        await repository.upsertAndPromote(
          project(
            id: 'uuid-alpha',
            canonicalPath: '/Users/dev/alpha',
            accessedAt: refreshedAccess,
          ),
        );

        final List<LocalProjectEntity> recent = await repository.listRecent();

        expect(recent, hasLength(2));
        expect(recent.first.id, 'uuid-alpha');
        expect(recent.first.lastAccessedAt, refreshedAccess);
        expect(recent.last.id, 'uuid-beta');
      },
    );

    test('migrates v1 persisted JSON to v2 on first read', () async {
      SharedPreferences.setMockInitialValues(<String, Object>{
        RecentProjectsLocalStorage.storageKey:
            '{"schemaVersion":1,"activeProjectId":"/Users/dev/first","projects":[{"id":"/Users/dev/first","absolutePath":"/Users/dev/first","displayName":"first","lastAccessedAtIso":"2026-05-14T12:00:00.000Z"},{"id":"/Users/dev/second","absolutePath":"/Users/dev/second","displayName":"second","lastAccessedAtIso":"2026-05-15T12:00:00.000Z"}]}',
      });
      final SharedPreferences preferences =
          await SharedPreferences.getInstance();
      var migrationIndex = 0;
      final RecentProjectsRepositoryImpl migratingRepository =
          RecentProjectsRepositoryImpl(
            RecentProjectsLocalStorage(preferences),
            migrateRecentProjectsUseCase: MigrateRecentProjectsUseCase(
              newProjectId: () {
                migrationIndex++;
                return 'migrated-uuid-$migrationIndex';
              },
            ),
          );

      final List<LocalProjectEntity> recent = await migratingRepository
          .listRecent();

      expect(recent, hasLength(2));
      expect(
        recent.every((LocalProjectEntity p) => p.id != p.canonicalPath),
        isTrue,
      );
      expect(recent.map((LocalProjectEntity p) => p.canonicalPath), <String>[
        '/Users/dev/first',
        '/Users/dev/second',
      ]);

      final String? activeId = await migratingRepository.getActiveProjectId();
      expect(activeId, isNotNull);
      expect(activeId, isNot('/Users/dev/first'));
      expect(recent.any((LocalProjectEntity p) => p.id == activeId), isTrue);

      final String? raw = RecentProjectsLocalStorage(preferences).readRaw();
      final RecentProjectsDocument? persisted = RecentProjectsDocument.tryParse(
        raw,
      );
      expect(
        persisted?.schemaVersion,
        RecentProjectsDocument.currentSchemaVersion,
      );
    });
  });

  group('RecentProjectsDocument', () {
    test('encode and tryParse round-trip v2 document fields', () {
      final RecentProjectsDocument document = RecentProjectsDocument(
        schemaVersion: RecentProjectsDocument.currentSchemaVersion,
        activeProjectId: 'uuid-team',
        projects: <LocalProjectEntity>[
          LocalProjectEntity(
            id: 'uuid-team',
            canonicalPath: '/Users/dev/team-repo',
            displayName: 'team-repo',
            lastAccessedAt: DateTime.utc(2026, 5, 15, 12),
          ),
        ],
      );

      final RecentProjectsDocument? parsed = RecentProjectsDocument.tryParse(
        document.encode(),
      );

      expect(parsed, isNotNull);
      expect(parsed!.schemaVersion, 2);
      expect(parsed.activeProjectId, 'uuid-team');
      expect(parsed.projects, hasLength(1));
      expect(parsed.projects.first.canonicalPath, '/Users/dev/team-repo');
    });

    test('tryParse accepts legacy v1 project rows with absolutePath', () {
      const String v1Json =
          '{"schemaVersion":1,"projects":[{"id":"/Users/dev/team-repo","absolutePath":"/Users/dev/team-repo","displayName":"team-repo","lastAccessedAtIso":"2026-05-15T12:00:00.000Z"}]}';

      final RecentProjectsDocument? parsed = RecentProjectsDocument.tryParse(
        v1Json,
      );

      expect(parsed, isNotNull);
      expect(parsed!.schemaVersion, 1);
      expect(parsed.projects.single.canonicalPath, '/Users/dev/team-repo');
    });
  });
}
