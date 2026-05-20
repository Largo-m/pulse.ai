import 'package:pulse_ai/features/orchestrator/data/models/recent_projects_document.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:uuid/uuid.dart';

final class MigrateRecentProjectsUseCase {
  MigrateRecentProjectsUseCase({String Function()? newProjectId})
    : _newProjectId = newProjectId ?? _defaultNewProjectId;

  static const Uuid _uuid = Uuid();

  static String _defaultNewProjectId() => _uuid.v4();

  final String Function() _newProjectId;

  RecentProjectsDocument call(RecentProjectsDocument document) {
    if (document.schemaVersion >= RecentProjectsDocument.currentSchemaVersion) {
      return document;
    }

    if (document.schemaVersion != RecentProjectsDocument.legacySchemaVersion) {
      return RecentProjectsDocument.empty();
    }

    final Map<String, String> legacyIdToUuid = <String, String>{};
    final List<LocalProjectEntity> migratedProjects = <LocalProjectEntity>[];

    for (final LocalProjectEntity project in document.projects) {
      final String uuid = _newProjectId();
      legacyIdToUuid[project.id] = uuid;
      migratedProjects.add(
        LocalProjectEntity(
          id: uuid,
          canonicalPath: project.canonicalPath,
          displayName: project.displayName,
          lastAccessedAt: project.lastAccessedAt,
          macosSecurityScopedBookmark: project.macosSecurityScopedBookmark,
        ),
      );
    }

    final String? legacyActiveId = document.activeProjectId;
    final String? migratedActiveId = legacyActiveId == null
        ? null
        : legacyIdToUuid[legacyActiveId];

    return RecentProjectsDocument(
      schemaVersion: RecentProjectsDocument.currentSchemaVersion,
      activeProjectId: migratedActiveId,
      projects: List<LocalProjectEntity>.unmodifiable(migratedProjects),
    );
  }
}
