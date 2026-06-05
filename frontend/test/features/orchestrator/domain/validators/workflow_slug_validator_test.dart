import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/validators/workflow_slug_validator.dart';

void main() {
  group('WorkflowSlugValidator', () {
    const WorkflowSlugValidator validator = WorkflowSlugValidator();

    test('validate returns right for kebab-case slug', () {
      expect(validator.validate('cursor-workflow-agents').isRight(), isTrue);
    });

    test('validate returns left for invalid slug format', () {
      final Either<Failure, void> result = validator.validate('Bad_Slug');
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
