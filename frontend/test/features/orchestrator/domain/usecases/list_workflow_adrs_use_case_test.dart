import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_workflow_adrs_use_case.dart';

void main() {
  group('ListWorkflowAdrsUseCase', () {
    test('returns empty list when workflow has no ADRs', () async {
      final FakeArtifactRepository repository = FakeArtifactRepository();
      final ListWorkflowAdrsUseCase useCase = ListWorkflowAdrsUseCase(
        repository,
      );

      final Either<Failure, List<AdrEntry>> result = await useCase(
        projectId: '550e8400-e29b-41d4-a716-446655440000',
        slug: 'cursor-workflow-agents',
      );

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (List<AdrEntry> adrs) {
        expect(adrs, isEmpty);
      });
    });

    test(
      'returns ADRs scoped to workflow slug without cross-binding',
      () async {
        const String projectId = '550e8400-e29b-41d4-a716-446655440000';
        final FakeArtifactRepository repository = FakeArtifactRepository();
        final ListWorkflowAdrsUseCase useCase = ListWorkflowAdrsUseCase(
          repository,
        );
        final String keyA = WorkflowKey.compose(
          projectId: projectId,
          slug: 'workflow-a',
        );
        final String keyB = WorkflowKey.compose(
          projectId: projectId,
          slug: 'workflow-b',
        );
        repository.adrsByKey[keyA] = <AdrEntry>[
          const AdrEntry(
            fileName: 'adr-a.md',
            sequenceNumber: 1,
            markdown: 'A',
          ),
        ];
        repository.adrsByKey[keyB] = <AdrEntry>[
          const AdrEntry(
            fileName: 'adr-b.md',
            sequenceNumber: 1,
            markdown: 'B',
          ),
        ];

        final Either<Failure, List<AdrEntry>> resultA = await useCase(
          projectId: projectId,
          slug: 'workflow-a',
        );
        final Either<Failure, List<AdrEntry>> resultB = await useCase(
          projectId: projectId,
          slug: 'workflow-b',
        );

        resultA.fold((_) => fail('expected right'), (List<AdrEntry> adrs) {
          expect(adrs.single.fileName, 'adr-a.md');
        });
        resultB.fold((_) => fail('expected right'), (List<AdrEntry> adrs) {
          expect(adrs.single.fileName, 'adr-b.md');
        });
      },
    );
  });
}
