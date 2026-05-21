import 'package:pulse_ai/core/error/failure.dart';

enum WorkflowPersistenceFailureCode {
  slugCollision,
  hiveError,
  invalidInput,
  invalidSlug,
}

final class WorkflowPersistenceFailure implements Failure {
  const WorkflowPersistenceFailure({required this.code, required this.message});

  const WorkflowPersistenceFailure.slugCollision()
    : this(
        code: WorkflowPersistenceFailureCode.slugCollision,
        message: 'Já existe um workflow com este slug neste projeto',
      );

  const WorkflowPersistenceFailure.hiveError()
    : this(
        code: WorkflowPersistenceFailureCode.hiveError,
        message: 'Falha ao persistir workflow',
      );

  const WorkflowPersistenceFailure.invalidInput(String detail)
    : this(code: WorkflowPersistenceFailureCode.invalidInput, message: detail);

  const WorkflowPersistenceFailure.invalidSlug()
    : this(
        code: WorkflowPersistenceFailureCode.invalidSlug,
        message: 'O slug do workflow deve estar em kebab-case',
      );

  final WorkflowPersistenceFailureCode code;
  @override
  final String message;
}
