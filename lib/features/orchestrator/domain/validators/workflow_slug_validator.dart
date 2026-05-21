import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/workflow_persistence_failure.dart';

final class WorkflowSlugValidator {
  const WorkflowSlugValidator();

  static final RegExp _kebabCasePattern = RegExp(r'^[a-z0-9]+(-[a-z0-9]+)*$');

  Either<Failure, void> validate(String slug) {
    if (!_kebabCasePattern.hasMatch(slug)) {
      return left(const WorkflowPersistenceFailure.invalidSlug());
    }
    return right(null);
  }
}
