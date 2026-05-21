import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';

final class FailPrdAgentRunUseCase {
  FailPrdAgentRunUseCase({
    required PrdRunRepository prdRunRepository,
    required WorkflowRepository workflowRepository,
    DateTime Function()? clock,
  }) : _prdRunRepository = prdRunRepository,
       _workflowRepository = workflowRepository,
       _clock = clock ?? DateTime.now;

  final PrdRunRepository _prdRunRepository;
  final WorkflowRepository _workflowRepository;
  final DateTime Function() _clock;

  Future<Either<Failure, PrdRunEntity>> call({
    required String runId,
    required String projectId,
    required String slug,
  }) async {
    final PrdRunEntity? run = await _prdRunRepository.findRunById(runId);
    if (run == null) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }

    final DateTime endedAt = _clock().toUtc();
    final PrdRunEntity failedRun = PrdRunEntity(
      id: run.id,
      workflowKey: run.workflowKey,
      cloudRunId: run.cloudRunId,
      status: PrdRunStatus.failed,
      supersedesRunId: run.supersedesRunId,
      feedback: run.feedback,
      startedAt: run.startedAt,
      endedAt: endedAt,
    );

    final Either<Failure, PrdRunEntity> updateResult = await _prdRunRepository
        .updateRun(failedRun);
    if (updateResult.isLeft()) {
      return updateResult;
    }

    final workflow = await _workflowRepository.findBySlug(
      projectId: projectId,
      slug: slug,
    );
    if (workflow == null) {
      return left(const PrdRunFailure.workflowNotFound());
    }

    final Either<Failure, void> phaseResult = await _workflowRepository.update(
      workflow.copyWith(prdPhaseStatus: PrdPhaseStatus.draft),
    );
    if (phaseResult.isLeft()) {
      return left(phaseResult.getLeft().toNullable()!);
    }

    return updateResult;
  }
}
