import 'dart:convert';

import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';

final class RecentProjectsDocument {
  const RecentProjectsDocument({
    required this.schemaVersion,
    required this.projects,
    this.activeProjectId,
  });

  static const int currentSchemaVersion = 1;

  final int schemaVersion;
  final String? activeProjectId;
  final List<LocalProjectEntity> projects;

  String encode() {
    return jsonEncode(toJson());
  }

  Map<String, Object?> toJson() {
    return <String, Object?>{
      'schemaVersion': schemaVersion,
      'activeProjectId': activeProjectId,
      'projects': projects.map(_projectToJson).toList(growable: false),
    };
  }

  static RecentProjectsDocument empty() {
    return const RecentProjectsDocument(
      schemaVersion: currentSchemaVersion,
      projects: <LocalProjectEntity>[],
    );
  }

  static RecentProjectsDocument? tryParse(String? rawJson) {
    if (rawJson == null || rawJson.isEmpty) {
      return null;
    }

    try {
      final Object? decoded = jsonDecode(rawJson);
      if (decoded is! Map<String, Object?>) {
        return null;
      }

      final Object? schemaVersionValue = decoded['schemaVersion'];
      if (schemaVersionValue is! int) {
        return null;
      }

      final String? activeProjectId = decoded['activeProjectId'] as String?;
      final Object? projectsValue = decoded['projects'];
      if (projectsValue is! List<Object?>) {
        return null;
      }

      final List<LocalProjectEntity> projects = <LocalProjectEntity>[];
      for (final Object? entry in projectsValue) {
        final LocalProjectEntity? project = _projectFromJson(entry);
        if (project == null) {
          return null;
        }
        projects.add(project);
      }

      return RecentProjectsDocument(
        schemaVersion: schemaVersionValue,
        activeProjectId: activeProjectId,
        projects: List<LocalProjectEntity>.unmodifiable(projects),
      );
    } on Object {
      return null;
    }
  }

  static Map<String, Object?> _projectToJson(LocalProjectEntity project) {
    return <String, Object?>{
      'id': project.id,
      'absolutePath': project.absolutePath,
      'displayName': project.displayName,
      'lastAccessedAtIso': project.lastAccessedAt.toUtc().toIso8601String(),
      if (project.macosSecurityScopedBookmark != null)
        'macosSecurityScopedBookmark': project.macosSecurityScopedBookmark,
    };
  }

  static LocalProjectEntity? _projectFromJson(Object? entry) {
    if (entry is! Map<String, Object?>) {
      return null;
    }

    final String? id = entry['id'] as String?;
    final String? absolutePath = entry['absolutePath'] as String?;
    final String? displayName = entry['displayName'] as String?;
    final String? lastAccessedAtIso = entry['lastAccessedAtIso'] as String?;

    if (id == null ||
        absolutePath == null ||
        displayName == null ||
        lastAccessedAtIso == null) {
      return null;
    }

    final DateTime? lastAccessedAt = DateTime.tryParse(lastAccessedAtIso);
    if (lastAccessedAt == null) {
      return null;
    }

    return LocalProjectEntity(
      id: id,
      absolutePath: absolutePath,
      displayName: displayName,
      lastAccessedAt: lastAccessedAt,
      macosSecurityScopedBookmark:
          entry['macosSecurityScopedBookmark'] as String?,
    );
  }
}
