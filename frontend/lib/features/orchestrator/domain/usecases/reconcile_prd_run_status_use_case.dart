import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/cloud_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_reconcile_result.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status_extensions.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';

final class ReconcilePrdRunStatusUseCase {
  ReconcilePrdRunStatusUseCase({
    required CursorCredentialStoreService credentialStore,
    required CursorPrdAgentService cursorPrdAgentService,
    required PrdRunRepository prdRunRepository,
    required WorkflowRepository workflowRepository,
    DateTime Function()? clock,
  }) : _credentialStore = credentialStore,
       _cursorPrdAgentService = cursorPrdAgentService,
       _prdRunRepository = prdRunRepository,
       _workflowRepository = workflowRepository,
       _clock = clock ?? DateTime.now;

  final CursorCredentialStoreService _credentialStore;
  final CursorPrdAgentService _cursorPrdAgentService;
  final PrdRunRepository _prdRunRepository;
  final WorkflowRepository _workflowRepository;
  final DateTime Function() _clock;

  Future<Either<Failure, PrdRunReconcileResult>> call(PrdRunEntity run) async {
    if (run.status.isTerminal) {
      return right(
        const PrdRunReconcileResult(
          outcome: PrdRunReconcileOutcome.skippedAlreadyTerminal,
        ),
      );
    }

    final String? cloudRunId = run.cloudRunId;
    if (cloudRunId == null || cloudRunId.isEmpty) {
      return right(
        const PrdRunReconcileResult(
          outcome: PrdRunReconcileOutcome.skippedNoCloudRunId,
        ),
      );
    }

    final String? credential = await _credentialStore.read();
    if (credential == null || credential.trim().isEmpty) {
      return right(
        const PrdRunReconcileResult(
          outcome: PrdRunReconcileOutcome.skippedNoCredential,
        ),
      );
    }

    final Either<Failure, CloudRunStatus> statusResult =
        await _cursorPrdAgentService.fetchRunStatus(cloudRunId);
    if (statusResult.isLeft()) {
      return left(statusResult.getLeft().toNullable()!);
    }

    final PrdRunStatus mappedStatus = statusResult
        .getRight()
        .toNullable()!
        .mappedPrdRunStatus;
    if (!mappedStatus.isTerminal) {
      return right(
        const PrdRunReconcileResult(outcome: PrdRunReconcileOutcome.unchanged),
      );
    }

    if (mappedStatus == run.status) {
      return right(
        const PrdRunReconcileResult(outcome: PrdRunReconcileOutcome.unchanged),
      );
    }

    final DateTime endedAt = _clock().toUtc();
    final PrdRunEntity reconciledRun = PrdRunEntity(
      id: run.id,
      workflowKey: run.workflowKey,
      cloudRunId: run.cloudRunId,
      status: mappedStatus,
      supersedesRunId: run.supersedesRunId,
      feedback: run.feedback,
      startedAt: run.startedAt,
      endedAt: endedAt,
    );

    final Either<Failure, PrdRunEntity> updateResult = await _prdRunRepository
        .updateRun(reconciledRun);
    if (updateResult.isLeft()) {
      return left(updateResult.getLeft().toNullable()!);
    }

    final ({String projectId, String slug})? keyParts = WorkflowKey.parse(
      run.workflowKey,
    );
    if (keyParts == null) {
      return left(const PrdRunFailure.workflowNotFound());
    }

    final workflow = await _workflowRepository.findBySlug(
      projectId: keyParts.projectId,
      slug: keyParts.slug,
    );
    if (workflow == null) {
      return left(const PrdRunFailure.workflowNotFound());
    }

    final PrdPhaseStatus? phaseStatus = _phaseForTerminalStatus(mappedStatus);
    if (phaseStatus != null) {
      final Either<Failure, void> phaseResult = await _workflowRepository
          .update(workflow.copyWith(prdPhaseStatus: phaseStatus));
      if (phaseResult.isLeft()) {
        return left(phaseResult.getLeft().toNullable()!);
      }
    }

    return right(
      PrdRunReconcileResult(
        outcome: PrdRunReconcileOutcome.updated,
        run: updateResult.getRight().toNullable(),
      ),
    );
  }

  PrdPhaseStatus? _phaseForTerminalStatus(PrdRunStatus status) {
    return switch (status) {
      PrdRunStatus.completed => PrdPhaseStatus.pendingApproval,
      PrdRunStatus.failed || PrdRunStatus.cancelled => PrdPhaseStatus.draft,
      _ => null,
    };
  }
}
