import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';

final class SelectActiveProjectUseCase {
  SelectActiveProjectUseCase(this._repository);

  final RecentProjectsRepository _repository;

  Future<void> select(String projectId) {
    return _repository.setActiveProjectId(projectId);
  }

  Future<String?> readActiveProjectId() {
    return _repository.getActiveProjectId();
  }

  Future<void> reconcileActiveWithRecentProjects() async {
    final String? activeProjectId = await _repository.getActiveProjectId();
    if (activeProjectId == null) {
      return;
    }

    final bool isActiveProjectKnown = (await _repository.listRecent()).any(
      (project) => project.id == activeProjectId,
    );

    if (!isActiveProjectKnown) {
      await _repository.setActiveProjectId(null);
    }
  }
}
