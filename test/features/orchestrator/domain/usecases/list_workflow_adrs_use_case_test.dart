import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/adr_entry.dart';
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
  });
}
