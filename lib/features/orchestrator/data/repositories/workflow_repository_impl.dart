import 'dart:io';

import 'package:fpdart/fpdart.dart';
import 'package:hive/hive.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/data/artifact_path_segment_validator.dart';
import 'package:pulse_ai/features/orchestrator/data/filesystem_artifact_store.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/data/persistence/persistence_write_coordinator.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';

typedef WorkflowHivePut =
    Future<void> Function(String key, WorkflowEntity entity);

final class WorkflowRepositoryImpl implements WorkflowRepository {
  WorkflowRepositoryImpl({
    required OrchestratorHiveBoxes boxes,
    FilesystemArtifactStore? artifactStore,
    ArtifactPathSegmentValidator? pathSegmentValidator,
    PersistenceWriteCoordinator? writeCoordinator,
    WorkflowHivePut? hivePutOverride,
  }) : _workflowsBox = boxes.workflows,
       _artifactStore = artifactStore,
       _pathSegmentValidator =
           pathSegmentValidator ?? const ArtifactPathSegmentValidator(),
       _writeCoordinator =
           writeCoordinator ?? const PersistenceWriteCoordinator(),
       _hivePutOverride = hivePutOverride;

  final Box<WorkflowEntity> _workflowsBox;
  final FilesystemArtifactStore? _artifactStore;
  final ArtifactPathSegmentValidator _pathSegmentValidator;
  final PersistenceWriteCoordinator _writeCoordinator;
  final WorkflowHivePut? _hivePutOverride;

  @override
  Future<Either<Failure, WorkflowEntity>> create({
    required String projectId,
    required String slug,
    required String branchName,
    String? directive,
  }) async {
    final Either<Failure, void> validation = _validateSegments(
      projectId: projectId,
      slug: slug,
    );
    if (validation.isLeft()) {
      return left(validation.getLeft().toNullable()!);
    }

    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    if (_workflowsBox.containsKey(key)) {
      return left(const WorkflowPersistenceFailure.slugCollision());
    }

    final WorkflowEntity entity = WorkflowEntity(
      projectId: projectId,
      slug: slug,
      branchName: branchName,
      directive: directive,
      prdPhaseStatus: PrdPhaseStatus.draft,
      createdAt: DateTime.now().toUtc(),
    );

    if (_artifactStore == null) {
      return _persistWorkflowIndex(key: key, entity: entity);
    }

    final FilesystemArtifactStore artifactStore = _artifactStore;
    return _writeCoordinator.commitFilesystemFirst<WorkflowEntity>(
      filesystemCommit: () async {
        try {
          final Directory directory = artifactStore.workflowDirectory(
            projectId: projectId,
            slug: slug,
          );
          await directory.create(recursive: true);
          return right(null);
        } on Object {
          return left(const ArtifactPersistenceFailure.ioError());
        }
      },
      hiveCommit: () => _persistWorkflowIndex(key: key, entity: entity),
      rollbackFilesystem: () async {
        final Directory directory = artifactStore.workflowDirectory(
          projectId: projectId,
          slug: slug,
        );
        if (await directory.exists()) {
          await directory.delete(recursive: true);
        }
      },
    );
  }

  @override
  Future<Either<Failure, List<WorkflowEntity>>> listByProject(
    String projectId,
  ) async {
    final Either<Failure, void> projectValidation = _pathSegmentValidator
        .validateProjectId(projectId);
    if (projectValidation.isLeft()) {
      return left(projectValidation.getLeft().toNullable()!);
    }

    try {
      final List<WorkflowEntity> workflows =
          _workflowsBox.values
              .where(
                (WorkflowEntity workflow) => workflow.projectId == projectId,
              )
              .toList(growable: false)
            ..sort(
              (WorkflowEntity a, WorkflowEntity b) =>
                  b.createdAt.compareTo(a.createdAt),
            );
      return right(workflows);
    } on Object {
      return left(const WorkflowPersistenceFailure.hiveError());
    }
  }

  @override
  Future<WorkflowEntity?> findBySlug({
    required String projectId,
    required String slug,
  }) async {
    final Either<Failure, void> validation = _validateSegments(
      projectId: projectId,
      slug: slug,
    );
    if (validation.isLeft()) {
      return null;
    }

    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    return _workflowsBox.get(key);
  }

  Either<Failure, void> _validateSegments({
    required String projectId,
    required String slug,
  }) {
    final Either<Failure, void> projectValidation = _pathSegmentValidator
        .validateProjectId(projectId);
    if (projectValidation.isLeft()) {
      return projectValidation;
    }
    return _pathSegmentValidator.validateSlug(slug);
  }

  Future<Either<Failure, WorkflowEntity>> _persistWorkflowIndex({
    required String key,
    required WorkflowEntity entity,
  }) async {
    try {
      if (_hivePutOverride != null) {
        await _hivePutOverride(key, entity);
      } else {
        await _workflowsBox.put(key, entity);
      }
      return right(entity);
    } on Object {
      return left(const WorkflowPersistenceFailure.hiveError());
    }
  }
}
