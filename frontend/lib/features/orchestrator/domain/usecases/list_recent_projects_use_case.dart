import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';

final class ListRecentProjectsUseCase {
  ListRecentProjectsUseCase(this._repository);

  final RecentProjectsRepository _repository;

  Future<List<LocalProjectEntity>> call() async {
    final List<LocalProjectEntity> projects = await _repository.listRecent();
    final List<LocalProjectEntity> sorted =
        List<LocalProjectEntity>.from(projects)..sort(
          (LocalProjectEntity a, LocalProjectEntity b) =>
              b.lastAccessedAt.compareTo(a.lastAccessedAt),
        );
    return List<LocalProjectEntity>.unmodifiable(sorted);
  }
}
