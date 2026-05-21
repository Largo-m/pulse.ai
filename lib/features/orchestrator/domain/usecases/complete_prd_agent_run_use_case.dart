import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_agent_run_output.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/workflow_repository.dart';

final class CompletePrdAgentRunUseCase {
  CompletePrdAgentRunUseCase({
    required PrdRunRepository prdRunRepository,
    required WorkflowRepository workflowRepository,
    required ArtifactRepository artifactRepository,
    DateTime Function()? clock,
  }) : _prdRunRepository = prdRunRepository,
       _workflowRepository = workflowRepository,
       _artifactRepository = artifactRepository,
       _clock = clock ?? DateTime.now;

  final PrdRunRepository _prdRunRepository;
  final WorkflowRepository _workflowRepository;
  final ArtifactRepository _artifactRepository;
  final DateTime Function() _clock;

  Future<Either<Failure, PrdRunEntity>> call({
    required String runId,
    required String projectId,
    required String slug,
    required PrdAgentRunOutput output,
  }) async {
    final PrdRunEntity? run = await _prdRunRepository.findRunById(runId);
    if (run == null) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }

    final DateTime completedAt = _clock().toUtc();
    final Either<Failure, void> prdWriteResult = await _artifactRepository
        .writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: output.prdMarkdown,
          metadata: PrdArtifactMetadata(
            lastEditedAt: completedAt,
            sourceRunId: runId,
          ),
        );
    if (prdWriteResult.isLeft()) {
      return left(prdWriteResult.getLeft().toNullable()!);
    }

    for (final AdrEntry entry in output.adrs) {
      final Either<Failure, void> adrResult = await _artifactRepository
          .writeAdrMarkdown(projectId: projectId, slug: slug, entry: entry);
      if (adrResult.isLeft()) {
        return left(adrResult.getLeft().toNullable()!);
      }
    }

    final workflow = await _workflowRepository.findBySlug(
      projectId: projectId,
      slug: slug,
    );
    if (workflow == null) {
      return left(const PrdRunFailure.workflowNotFound());
    }

    final Either<Failure, void> phaseResult = await _workflowRepository.update(
      workflow.copyWith(prdPhaseStatus: PrdPhaseStatus.pendingApproval),
    );
    if (phaseResult.isLeft()) {
      return left(phaseResult.getLeft().toNullable()!);
    }

    final Either<Failure, void> approvalResult = await _prdRunRepository
        .upsertApproval(
          workflowKey: run.workflowKey,
          status: PrdApprovalStatus.pendingApproval,
          sourceRunId: runId,
        );
    if (approvalResult.isLeft()) {
      return left(approvalResult.getLeft().toNullable()!);
    }

    final PrdRunEntity completedRun = PrdRunEntity(
      id: run.id,
      workflowKey: run.workflowKey,
      cloudRunId: run.cloudRunId,
      status: PrdRunStatus.completed,
      supersedesRunId: run.supersedesRunId,
      feedback: run.feedback,
      startedAt: run.startedAt,
      endedAt: completedAt,
    );

    return _prdRunRepository.updateRun(completedRun);
  }
}
