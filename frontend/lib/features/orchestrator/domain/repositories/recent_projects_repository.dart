import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';

abstract interface class RecentProjectsRepository {
  Future<List<LocalProjectEntity>> listRecent();

  Future<String?> getActiveProjectId();

  Future<void> upsertAndPromote(LocalProjectEntity project);

  Future<void> replaceRecentProjects(List<LocalProjectEntity> projects);

  Future<void> setActiveProjectId(String? projectId);
}
