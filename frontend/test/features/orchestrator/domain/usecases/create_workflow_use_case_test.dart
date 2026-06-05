import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/create_workflow_use_case.dart';

void main() {
  group('CreateWorkflowUseCase', () {
    const String projectId = '550e8400-e29b-41d4-a716-446655440000';
    const String branchName = 'main';

    test('persists workflow when slug is valid kebab-case', () async {
      final FakeWorkflowRepository repository = FakeWorkflowRepository();
      final CreateWorkflowUseCase useCase = CreateWorkflowUseCase(
        workflowRepository: repository,
      );

      final Either<Failure, WorkflowEntity> result = await useCase(
        projectId: projectId,
        slug: 'cursor-workflow-agents',
        branchName: branchName,
      );

      expect(result.isRight(), isTrue);
      result.fold((_) => fail('expected right'), (WorkflowEntity workflow) {
        expect(workflow.slug, 'cursor-workflow-agents');
        expect(workflow.projectId, projectId);
      });
    });

    test(
      'returns slug collision failure for duplicate slug in same project',
      () async {
        final FakeWorkflowRepository repository = FakeWorkflowRepository();
        final CreateWorkflowUseCase useCase = CreateWorkflowUseCase(
          workflowRepository: repository,
        );
        const String slug = 'payments-api';

        await useCase(projectId: projectId, slug: slug, branchName: branchName);

        final Either<Failure, WorkflowEntity> second = await useCase(
          projectId: projectId,
          slug: slug,
          branchName: 'develop',
        );

        expect(second.isLeft(), isTrue);
        second.fold(
          (Failure failure) => expect(
            failure,
            isA<WorkflowPersistenceFailure>().having(
              (WorkflowPersistenceFailure f) => f.code,
              'code',
              WorkflowPersistenceFailureCode.slugCollision,
            ),
          ),
          (_) => fail('expected left'),
        );
      },
    );

    test('returns validation failure when slug is not kebab-case', () async {
      final FakeWorkflowRepository repository = FakeWorkflowRepository();
      final CreateWorkflowUseCase useCase = CreateWorkflowUseCase(
        workflowRepository: repository,
      );

      final Either<Failure, WorkflowEntity> result = await useCase(
        projectId: projectId,
        slug: 'Bad_Slug',
        branchName: branchName,
      );

      expect(result.isLeft(), isTrue);
      result.fold(
        (Failure failure) => expect(
          failure,
          isA<WorkflowPersistenceFailure>().having(
            (WorkflowPersistenceFailure f) => f.code,
            'code',
            WorkflowPersistenceFailureCode.invalidSlug,
          ),
        ),
        (_) => fail('expected left'),
      );
    });
  });
}
