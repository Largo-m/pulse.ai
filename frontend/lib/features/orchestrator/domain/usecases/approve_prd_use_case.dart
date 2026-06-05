import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';

final class ApprovePrdUseCase {
  ApprovePrdUseCase({
    required PrdRunRepository prdRunRepository,
    required WorkflowRepository workflowRepository,
    DateTime Function()? clock,
  }) : _prdRunRepository = prdRunRepository,
       _workflowRepository = workflowRepository,
       _clock = clock ?? DateTime.now;

  final PrdRunRepository _prdRunRepository;
  final WorkflowRepository _workflowRepository;
  final DateTime Function() _clock;

  Future<Either<Failure, PrdApprovalEntity>> call({
    required String projectId,
    required String slug,
  }) async {
    final workflow = await _workflowRepository.findBySlug(
      projectId: projectId,
      slug: slug,
    );
    if (workflow == null) {
      return left(const PrdRunFailure.workflowNotFound());
    }

    final String workflowKey = WorkflowKey.compose(
      projectId: projectId,
      slug: slug,
    );
    final PrdApprovalEntity? existingApproval = await _prdRunRepository
        .findApproval(workflowKey);
    final DateTime approvedAt = _clock().toUtc();

    final Either<Failure, PrdApprovalEntity> approvalResult =
        await _prdRunRepository.upsertApproval(
          workflowKey: workflowKey,
          status: PrdApprovalStatus.approved,
          approvedAt: approvedAt,
          lastEditedAt: existingApproval?.lastEditedAt,
          sourceRunId: existingApproval?.sourceRunId,
        );
    if (approvalResult.isLeft()) {
      return approvalResult;
    }

    final Either<Failure, void> phaseResult = await _workflowRepository.update(
      workflow.copyWith(prdPhaseStatus: PrdPhaseStatus.approved),
    );
    if (phaseResult.isLeft()) {
      return left(phaseResult.getLeft().toNullable()!);
    }

    return approvalResult;
  }
}
