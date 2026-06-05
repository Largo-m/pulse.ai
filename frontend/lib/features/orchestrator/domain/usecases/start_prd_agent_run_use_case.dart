import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_connection_gate.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';

final class StartPrdAgentRunUseCase {
  StartPrdAgentRunUseCase({
    required PrdRunConnectionGate connectionGate,
    required BuildPrdRunContextUseCase buildPrdRunContextUseCase,
    required PrdRunRepository prdRunRepository,
    required WorkflowRepository workflowRepository,
    required CursorPrdAgentService cursorPrdAgentService,
    DateTime Function()? clock,
  }) : _connectionGate = connectionGate,
       _buildPrdRunContextUseCase = buildPrdRunContextUseCase,
       _prdRunRepository = prdRunRepository,
       _workflowRepository = workflowRepository,
       _cursorPrdAgentService = cursorPrdAgentService,
       _clock = clock ?? DateTime.now;

  final PrdRunConnectionGate _connectionGate;
  final BuildPrdRunContextUseCase _buildPrdRunContextUseCase;
  final PrdRunRepository _prdRunRepository;
  final WorkflowRepository _workflowRepository;
  final CursorPrdAgentService _cursorPrdAgentService;
  final DateTime Function() _clock;

  Future<Either<Failure, PrdRunEntity>> call(PrdRunRequest request) async {
    final Either<Failure, void> connectionResult = await _connectionGate
        .ensureCanStart();
    if (connectionResult.isLeft()) {
      return left(connectionResult.getLeft().toNullable()!);
    }

    final String workflowKey = WorkflowKey.compose(
      projectId: request.projectId,
      slug: request.slug,
    );

    final workflow = await _workflowRepository.findBySlug(
      projectId: request.projectId,
      slug: request.slug,
    );
    if (workflow == null) {
      return left(const PrdRunFailure.workflowNotFound());
    }

    final Either<Failure, PrdRunEntity> queuedResult = await _prdRunRepository
        .createRun(
          workflowKey: workflowKey,
          status: PrdRunStatus.queued,
          supersedesRunId: request.supersedesRunId,
          feedback: request.feedback,
        );
    if (queuedResult.isLeft()) {
      return queuedResult;
    }

    final PrdRunEntity queuedRun = queuedResult.getRight().toNullable()!;

    final Either<Failure, PrdRunContext> contextResult =
        await _buildPrdRunContextUseCase(request);
    if (contextResult.isLeft()) {
      await _markRunFailed(queuedRun);
      return left(contextResult.getLeft().toNullable()!);
    }

    try {
      final PrdRunEntity serviceRun = await _cursorPrdAgentService.startRun(
        contextResult.getRight().toNullable()!,
      );

      final PrdRunEntity runningRun = PrdRunEntity(
        id: queuedRun.id,
        workflowKey: queuedRun.workflowKey,
        cloudRunId: serviceRun.cloudRunId,
        status: PrdRunStatus.running,
        supersedesRunId: queuedRun.supersedesRunId,
        feedback: queuedRun.feedback,
        startedAt: queuedRun.startedAt,
      );

      final Either<Failure, PrdRunEntity> updateResult = await _prdRunRepository
          .updateRun(runningRun);
      if (updateResult.isLeft()) {
        return updateResult;
      }

      final Either<Failure, void> phaseResult = await _workflowRepository
          .update(workflow.copyWith(prdPhaseStatus: PrdPhaseStatus.running));
      if (phaseResult.isLeft()) {
        return left(phaseResult.getLeft().toNullable()!);
      }

      return updateResult;
    } on PrdRunOperationException catch (error) {
      await _markRunFailed(queuedRun);
      return left(error.failure);
    } on Object {
      await _markRunFailed(queuedRun);
      return left(const PrdRunFailure.cloudRunFailed());
    }
  }

  Future<void> _markRunFailed(PrdRunEntity run) async {
    await _prdRunRepository.updateRun(
      PrdRunEntity(
        id: run.id,
        workflowKey: run.workflowKey,
        cloudRunId: run.cloudRunId,
        status: PrdRunStatus.failed,
        supersedesRunId: run.supersedesRunId,
        feedback: run.feedback,
        startedAt: run.startedAt,
        endedAt: _clock().toUtc(),
      ),
    );
  }
}
