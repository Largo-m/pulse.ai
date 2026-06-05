import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/cancel_prd_agent_run_outcome.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';

final class CancelPrdAgentRunUseCase {
  CancelPrdAgentRunUseCase({
    required PrdRunRepository prdRunRepository,
    required WorkflowRepository workflowRepository,
    required CursorPrdAgentService cursorPrdAgentService,
    DateTime Function()? clock,
  }) : _prdRunRepository = prdRunRepository,
       _workflowRepository = workflowRepository,
       _cursorPrdAgentService = cursorPrdAgentService,
       _clock = clock ?? DateTime.now;

  final PrdRunRepository _prdRunRepository;
  final WorkflowRepository _workflowRepository;
  final CursorPrdAgentService _cursorPrdAgentService;
  final DateTime Function() _clock;

  Future<Either<Failure, CancelPrdAgentRunOutcome>> call({
    required String runId,
    required String projectId,
    required String slug,
  }) async {
    final PrdRunEntity? run = await _prdRunRepository.findRunById(runId);
    if (run == null) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }

    bool cloudCancelFailed = false;
    final String? cloudRunId = run.cloudRunId;
    if (cloudRunId != null && cloudRunId.isNotEmpty) {
      try {
        await _cursorPrdAgentService.cancelRun(cloudRunId);
      } on PrdRunOperationException catch (error) {
        if (error.failure is PrdRunFailure &&
            (error.failure as PrdRunFailure).code ==
                PrdRunFailureCode.cloudRunFailed) {
          cloudCancelFailed = true;
        } else {
          return left(error.failure);
        }
      }
    }

    final DateTime endedAt = _clock().toUtc();
    final PrdRunEntity cancelledRun = PrdRunEntity(
      id: run.id,
      workflowKey: run.workflowKey,
      cloudRunId: run.cloudRunId,
      status: PrdRunStatus.cancelled,
      supersedesRunId: run.supersedesRunId,
      feedback: run.feedback,
      startedAt: run.startedAt,
      endedAt: endedAt,
    );

    final Either<Failure, PrdRunEntity> updateResult = await _prdRunRepository
        .updateRun(cancelledRun);
    if (updateResult.isLeft()) {
      return left(updateResult.getLeft().toNullable()!);
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

    return right(
      CancelPrdAgentRunOutcome(
        run: updateResult.getRight().toNullable()!,
        cloudCancelFailed: cloudCancelFailed,
      ),
    );
  }
}
