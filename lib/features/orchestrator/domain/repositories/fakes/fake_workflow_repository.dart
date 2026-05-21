import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';

final class FakeWorkflowRepository implements WorkflowRepository {
  final Map<String, WorkflowEntity> _workflows = <String, WorkflowEntity>{};

  @override
  Future<Either<Failure, WorkflowEntity>> create({
    required String projectId,
    required String slug,
    required String branchName,
    String? directive,
  }) async {
    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    if (_workflows.containsKey(key)) {
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
    _workflows[key] = entity;
    return right(entity);
  }

  @override
  Future<Either<Failure, List<WorkflowEntity>>> listByProject(
    String projectId,
  ) async {
    final List<WorkflowEntity> workflows = _workflows.values
        .where((WorkflowEntity workflow) => workflow.projectId == projectId)
        .toList(growable: false);
    return right(workflows);
  }

  @override
  Future<WorkflowEntity?> findBySlug({
    required String projectId,
    required String slug,
  }) async {
    final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
    return _workflows[key];
  }

  @override
  Future<Either<Failure, WorkflowEntity>> update(
    WorkflowEntity workflow,
  ) async {
    final String key = workflow.workflowKey;
    if (!_workflows.containsKey(key)) {
      return left(const WorkflowPersistenceFailure.notFound());
    }
    _workflows[key] = workflow;
    return right(workflow);
  }
}
