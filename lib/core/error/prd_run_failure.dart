import 'package:pulse_ai/core/error/failure.dart';

enum PrdRunFailureCode {
  projectNotFound,
  branchInvalid,
  gitContextUnavailable,
  cloudRunFailed,
  cloudRunNotFound,
  streamUnavailable,
  cancelled,
}

final class PrdRunFailure implements Failure {
  const PrdRunFailure({required this.code, required this.message});

  const PrdRunFailure.projectNotFound()
    : this(code: PrdRunFailureCode.projectNotFound, message: '');

  const PrdRunFailure.branchInvalid()
    : this(code: PrdRunFailureCode.branchInvalid, message: '');

  const PrdRunFailure.gitContextUnavailable()
    : this(code: PrdRunFailureCode.gitContextUnavailable, message: '');

  const PrdRunFailure.cloudRunFailed()
    : this(code: PrdRunFailureCode.cloudRunFailed, message: '');

  const PrdRunFailure.cloudRunNotFound()
    : this(code: PrdRunFailureCode.cloudRunNotFound, message: '');

  const PrdRunFailure.streamUnavailable()
    : this(code: PrdRunFailureCode.streamUnavailable, message: '');

  final PrdRunFailureCode code;

  @override
  final String message;
}

final class PrdRunOperationException implements Exception {
  const PrdRunOperationException(this.failure);

  final Failure failure;
}
