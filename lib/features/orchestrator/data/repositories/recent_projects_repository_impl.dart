import 'package:pulse_ai/features/orchestrator/data/models/recent_projects_document.dart';
import 'package:pulse_ai/features/orchestrator/data/recent_projects_local_storage.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/migrate_recent_projects_use_case.dart';

final class RecentProjectsRepositoryImpl implements RecentProjectsRepository {
  RecentProjectsRepositoryImpl(
    this._storage, {
    MigrateRecentProjectsUseCase? migrateRecentProjectsUseCase,
  }) : _migrateRecentProjectsUseCase =
           migrateRecentProjectsUseCase ?? MigrateRecentProjectsUseCase();

  final RecentProjectsLocalStorage _storage;
  final MigrateRecentProjectsUseCase _migrateRecentProjectsUseCase;

  @override
  Future<List<LocalProjectEntity>> listRecent() async {
    final RecentProjectsDocument document = await _readDocument();
    return List<LocalProjectEntity>.unmodifiable(document.projects);
  }

  @override
  Future<String?> getActiveProjectId() async {
    final RecentProjectsDocument document = await _readDocument();
    return document.activeProjectId;
  }

  @override
  Future<void> upsertAndPromote(LocalProjectEntity project) async {
    final RecentProjectsDocument document = await _readDocument();
    final List<LocalProjectEntity> updatedProjects = <LocalProjectEntity>[
      project,
      ...document.projects.where(
        (LocalProjectEntity existing) => existing.id != project.id,
      ),
    ];

    await _writeDocument(
      RecentProjectsDocument(
        schemaVersion: RecentProjectsDocument.currentSchemaVersion,
        activeProjectId: document.activeProjectId,
        projects: updatedProjects,
      ),
    );
  }

  @override
  Future<void> replaceRecentProjects(List<LocalProjectEntity> projects) async {
    final RecentProjectsDocument document = await _readDocument();
    await _writeDocument(
      RecentProjectsDocument(
        schemaVersion: RecentProjectsDocument.currentSchemaVersion,
        activeProjectId: document.activeProjectId,
        projects: List<LocalProjectEntity>.unmodifiable(projects),
      ),
    );
  }

  @override
  Future<void> setActiveProjectId(String? projectId) async {
    final RecentProjectsDocument document = await _readDocument();
    await _writeDocument(
      RecentProjectsDocument(
        schemaVersion: RecentProjectsDocument.currentSchemaVersion,
        activeProjectId: projectId,
        projects: document.projects,
      ),
    );
  }

  Future<RecentProjectsDocument> _readDocument() async {
    final String? raw = _storage.readRaw();
    final RecentProjectsDocument parsed =
        RecentProjectsDocument.tryParse(raw) ?? RecentProjectsDocument.empty();
    final RecentProjectsDocument migrated = _migrateRecentProjectsUseCase.call(
      parsed,
    );

    if (migrated.schemaVersion != parsed.schemaVersion || migrated != parsed) {
      await _writeDocument(migrated);
    }

    return migrated;
  }

  Future<void> _writeDocument(RecentProjectsDocument document) async {
    await _storage.writeRaw(document.encode());
  }
}
