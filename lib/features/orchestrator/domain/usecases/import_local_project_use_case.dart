import 'package:path/path.dart' as p;
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/project_path_normalizer.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/recent_projects_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_directory_picker_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/import_local_project_result.dart';

final class ImportLocalProjectUseCase {
  ImportLocalProjectUseCase({
    required RecentProjectsRepository repository,
    required LocalDirectoryPickerService pickerService,
    ProjectPathNormalizer? pathNormalizer,
    DateTime Function()? clock,
    int maxRecentProjects = 10,
  }) : _repository = repository,
       _pickerService = pickerService,
       _pathNormalizer = pathNormalizer ?? const ProjectPathNormalizer(),
       _clock = clock ?? DateTime.now,
       _maxRecentProjects = maxRecentProjects;

  static const int defaultMaxRecentProjects = 10;

  final RecentProjectsRepository _repository;
  final LocalDirectoryPickerService _pickerService;
  final ProjectPathNormalizer _pathNormalizer;
  final DateTime Function() _clock;
  final int _maxRecentProjects;

  Future<ImportLocalProjectResult> call() async {
    final DirectoryPickResult pickResult = await _pickerService.pickDirectory();

    if (pickResult.outcome == DirectoryPickOutcome.cancelled) {
      return const ImportLocalProjectResult(
        ImportLocalProjectOutcome.cancelled,
      );
    }

    if (pickResult.outcome == DirectoryPickOutcome.failure) {
      return ImportLocalProjectResult(
        ImportLocalProjectOutcome.failure,
        failureMessage: pickResult.failureMessage,
      );
    }

    final String? rawPath = pickResult.absolutePath;
    if (rawPath == null || rawPath.trim().isEmpty) {
      return const ImportLocalProjectResult(
        ImportLocalProjectOutcome.failure,
        failureMessage: 'empty path',
      );
    }

    try {
      final String normalizedId = _pathNormalizer.normalizeToAbsoluteId(
        rawPath,
      );
      final DateTime accessedAt = _clock().toUtc();
      final LocalProjectEntity project = LocalProjectEntity(
        id: normalizedId,
        absolutePath: normalizedId,
        displayName: p.basename(normalizedId),
        lastAccessedAt: accessedAt,
      );

      await _repository.upsertAndPromote(project);
      await _enforceRecentProjectsCap();
      await _repository.setActiveProjectId(project.id);

      return ImportLocalProjectResult(
        ImportLocalProjectOutcome.success,
        project: project,
      );
    } on ArgumentError catch (error) {
      final String message = switch (error.message) {
        final String value => value,
        _ => error.toString(),
      };
      return ImportLocalProjectResult(
        ImportLocalProjectOutcome.failure,
        failureMessage: message,
      );
    }
  }

  Future<void> _enforceRecentProjectsCap() async {
    final List<LocalProjectEntity> recent = await _repository.listRecent();
    if (recent.length <= _maxRecentProjects) {
      return;
    }

    final List<LocalProjectEntity> sortedByOldestFirst =
        List<LocalProjectEntity>.from(recent)..sort(
          (LocalProjectEntity a, LocalProjectEntity b) =>
              a.lastAccessedAt.compareTo(b.lastAccessedAt),
        );

    final List<LocalProjectEntity> capped = sortedByOldestFirst
        .skip(recent.length - _maxRecentProjects)
        .toList(growable: false);

    await _repository.replaceRecentProjects(capped);
  }
}
