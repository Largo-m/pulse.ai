import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';

final class RejectPrdWithFeedbackUseCase {
  RejectPrdWithFeedbackUseCase({
    required PrdRunRepository prdRunRepository,
    required WorkflowRepository workflowRepository,
    required StartPrdAgentRunUseCase startPrdAgentRunUseCase,
  }) : _prdRunRepository = prdRunRepository,
       _workflowRepository = workflowRepository,
       _startPrdAgentRunUseCase = startPrdAgentRunUseCase;

  final PrdRunRepository _prdRunRepository;
  final WorkflowRepository _workflowRepository;
  final StartPrdAgentRunUseCase _startPrdAgentRunUseCase;

  Future<Either<Failure, PrdRunEntity>> call({
    required String projectId,
    required String slug,
    required String repoPath,
    required String rejectedRunId,
    required String feedback,
  }) async {
    final workflow = await _workflowRepository.findBySlug(
      projectId: projectId,
      slug: slug,
    );
    if (workflow == null) {
      return left(const PrdRunFailure.workflowNotFound());
    }

    final PrdRunEntity? rejectedRun = await _prdRunRepository.findRunById(
      rejectedRunId,
    );
    if (rejectedRun == null) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }

    final String workflowKey = WorkflowKey.compose(
      projectId: projectId,
      slug: slug,
    );
    if (rejectedRun.workflowKey != workflowKey) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }

    final Either<Failure, PrdRunEntity> feedbackUpdateResult =
        await _prdRunRepository.updateRun(
          PrdRunEntity(
            id: rejectedRun.id,
            workflowKey: rejectedRun.workflowKey,
            cloudRunId: rejectedRun.cloudRunId,
            status: rejectedRun.status,
            supersedesRunId: rejectedRun.supersedesRunId,
            feedback: feedback,
            startedAt: rejectedRun.startedAt,
            endedAt: rejectedRun.endedAt,
          ),
        );
    if (feedbackUpdateResult.isLeft()) {
      return left(feedbackUpdateResult.getLeft().toNullable()!);
    }

    final PrdApprovalEntity? existingApproval = await _prdRunRepository
        .findApproval(workflowKey);
    final Either<Failure, PrdApprovalEntity> approvalResetResult =
        await _prdRunRepository.upsertApproval(
          workflowKey: workflowKey,
          status: PrdApprovalStatus.draft,
          lastEditedAt: existingApproval?.lastEditedAt,
          sourceRunId: existingApproval?.sourceRunId,
        );
    if (approvalResetResult.isLeft()) {
      return left(approvalResetResult.getLeft().toNullable()!);
    }

    return _startPrdAgentRunUseCase(
      PrdRunRequest(
        projectId: projectId,
        slug: slug,
        repoPath: repoPath,
        branchName: workflow.branchName,
        directive: workflow.directive ?? '',
        feedback: feedback,
        supersedesRunId: rejectedRunId,
      ),
    );
  }
}
