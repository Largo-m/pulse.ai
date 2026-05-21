import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/create_workflow_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_workflows_by_project_use_case.dart';

void main() {
  group('ListWorkflowsByProjectUseCase', () {
    const String projectId = '550e8400-e29b-41d4-a716-446655440000';

    test('returns empty list when project has no workflows', () async {
      final FakeWorkflowRepository repository = FakeWorkflowRepository();
      final ListWorkflowsByProjectUseCase useCase =
          ListWorkflowsByProjectUseCase(repository);

      final Either<Failure, List<WorkflowEntity>> result = await useCase(
        projectId,
      );

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (List<WorkflowEntity> list) {
        expect(list, isEmpty);
      });
    });

    test('returns workflows for requested project only', () async {
      final FakeWorkflowRepository repository = FakeWorkflowRepository();
      final CreateWorkflowUseCase createUseCase = CreateWorkflowUseCase(
        workflowRepository: repository,
      );
      final ListWorkflowsByProjectUseCase listUseCase =
          ListWorkflowsByProjectUseCase(repository);

      await createUseCase(
        projectId: projectId,
        slug: 'feature-a',
        branchName: 'main',
      );
      await createUseCase(
        projectId: 'other-project',
        slug: 'feature-b',
        branchName: 'main',
      );

      final Either<Failure, List<WorkflowEntity>> result = await listUseCase(
        projectId,
      );

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (List<WorkflowEntity> list) {
        expect(list, hasLength(1));
        expect(list.first.slug, 'feature-a');
      });
    });
  });
}
