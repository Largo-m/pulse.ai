import 'package:pulse_ai/core/error/failure.dart';

enum PrdRunPersistenceFailureCode { hiveError, runNotFound, workflowNotFound }

final class PrdRunPersistenceFailure implements Failure {
  const PrdRunPersistenceFailure({required this.code, required this.message});

  const PrdRunPersistenceFailure.hiveError()
    : this(
        code: PrdRunPersistenceFailureCode.hiveError,
        message: 'Falha ao persistir execução PRD',
      );

  const PrdRunPersistenceFailure.runNotFound()
    : this(
        code: PrdRunPersistenceFailureCode.runNotFound,
        message: 'Execução PRD não encontrada',
      );

  const PrdRunPersistenceFailure.workflowNotFound()
    : this(
        code: PrdRunPersistenceFailureCode.workflowNotFound,
        message: 'Workflow não encontrado',
      );

  final PrdRunPersistenceFailureCode code;
  @override
  final String message;
}
