import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';

final class FakeRecentProjectsRepository implements RecentProjectsRepository {
  final List<LocalProjectEntity> projects = <LocalProjectEntity>[];
  String? activeProjectId;

  int upsertCallCount = 0;
  int replaceCallCount = 0;

  @override
  Future<List<LocalProjectEntity>> listRecent() async {
    return List<LocalProjectEntity>.unmodifiable(projects);
  }

  @override
  Future<String?> getActiveProjectId() async {
    return activeProjectId;
  }

  @override
  Future<void> upsertAndPromote(LocalProjectEntity project) async {
    upsertCallCount++;
    projects.removeWhere(
      (LocalProjectEntity existing) => existing.id == project.id,
    );
    projects.insert(0, project);
  }

  @override
  Future<void> replaceRecentProjects(
    List<LocalProjectEntity> updatedProjects,
  ) async {
    replaceCallCount++;
    projects
      ..clear()
      ..addAll(updatedProjects);
  }

  @override
  Future<void> setActiveProjectId(String? projectId) async {
    activeProjectId = projectId;
  }
}
