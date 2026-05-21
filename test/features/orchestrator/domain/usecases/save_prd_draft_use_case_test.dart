import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_artifact_metadata.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/read_prd_markdown_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_prd_draft_use_case.dart';

void main() {
  group('SavePrdDraftUseCase', () {
    const String projectId = '550e8400-e29b-41d4-a716-446655440000';
    const String slug = 'cursor-workflow-agents';
    const String markdown = '# PRD\n\nDraft content';
    final DateTime fixedNow = DateTime.utc(2026, 5, 20, 14, 30);

    test('writes markdown and updates lastEditedAt metadata', () async {
      final FakeArtifactRepository artifactRepository =
          FakeArtifactRepository();
      final FakePrdRunRepository prdRunRepository = FakePrdRunRepository();
      final SavePrdDraftUseCase saveUseCase = SavePrdDraftUseCase(
        artifactRepository: artifactRepository,
        prdRunRepository: prdRunRepository,
        clock: () => fixedNow,
      );

      final Either<Failure, void> saveResult = await saveUseCase(
        projectId: projectId,
        slug: slug,
        markdown: markdown,
      );

      expect(saveResult.isRight(), isTrue);

      final String key = WorkflowKey.compose(projectId: projectId, slug: slug);
      final PrdArtifactMetadata? metadata =
          artifactRepository.metadataByKey[key];
      expect(metadata?.lastEditedAt, fixedNow);

      final approval = await prdRunRepository.findApproval(key);
      expect(approval?.lastEditedAt, fixedNow);
      expect(approval?.status, PrdApprovalStatus.draft);
    });

    test(
      'read PRD returns content after save via fake artifact repo',
      () async {
        final FakeArtifactRepository artifactRepository =
            FakeArtifactRepository();
        final FakePrdRunRepository prdRunRepository = FakePrdRunRepository();
        final SavePrdDraftUseCase saveUseCase = SavePrdDraftUseCase(
          artifactRepository: artifactRepository,
          prdRunRepository: prdRunRepository,
        );
        final ReadPrdMarkdownUseCase readUseCase = ReadPrdMarkdownUseCase(
          artifactRepository,
        );

        await saveUseCase(projectId: projectId, slug: slug, markdown: markdown);

        final Either<Failure, String> readResult = await readUseCase(
          projectId: projectId,
          slug: slug,
        );

        expect(readResult.isRight(), isTrue);
        readResult.fold((_) => fail('expected right'), (String content) {
          expect(content, markdown);
        });
      },
    );
  });
}
