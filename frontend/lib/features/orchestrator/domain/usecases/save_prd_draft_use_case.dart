import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';

final class SavePrdDraftUseCase {
  SavePrdDraftUseCase({
    required ArtifactRepository artifactRepository,
    required PrdRunRepository prdRunRepository,
    DateTime Function()? clock,
  }) : _artifactRepository = artifactRepository,
       _prdRunRepository = prdRunRepository,
       _clock = clock ?? DateTime.now;

  final ArtifactRepository _artifactRepository;
  final PrdRunRepository _prdRunRepository;
  final DateTime Function() _clock;

  Future<Either<Failure, void>> call({
    required String projectId,
    required String slug,
    required String markdown,
  }) async {
    final DateTime lastEditedAt = _clock().toUtc();
    final String workflowKey = WorkflowKey.compose(
      projectId: projectId,
      slug: slug,
    );

    final Either<Failure, void> writeResult = await _artifactRepository
        .writePrdMarkdown(
          projectId: projectId,
          slug: slug,
          markdown: markdown,
          metadata: PrdArtifactMetadata(lastEditedAt: lastEditedAt),
        );
    if (writeResult.isLeft()) {
      return writeResult;
    }

    final PrdApprovalEntity? existingApproval = await _prdRunRepository
        .findApproval(workflowKey);
    final PrdApprovalStatus status =
        existingApproval?.status ?? PrdApprovalStatus.draft;

    final Either<Failure, PrdApprovalEntity> approvalResult =
        await _prdRunRepository.upsertApproval(
          workflowKey: workflowKey,
          status: status,
          lastEditedAt: lastEditedAt,
          sourceRunId: existingApproval?.sourceRunId,
          approvedAt: existingApproval?.approvedAt,
        );
    return approvalResult.fold(
      (Failure failure) => left(failure),
      (PrdApprovalEntity _) => right(null),
    );
  }
}
