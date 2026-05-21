import 'package:pulse_ai/core/error/failure.dart';

enum CursorConnectionFailureCode {
  missingCredential,
  unauthorized,
  network,
  unknown,
}

final class CursorConnectionFailure implements Failure {
  const CursorConnectionFailure({required this.code, required this.message});

  const CursorConnectionFailure.missingCredential()
    : this(code: CursorConnectionFailureCode.missingCredential, message: '');

  const CursorConnectionFailure.unauthorized()
    : this(code: CursorConnectionFailureCode.unauthorized, message: '');

  const CursorConnectionFailure.network()
    : this(code: CursorConnectionFailureCode.network, message: '');

  const CursorConnectionFailure.unknown()
    : this(code: CursorConnectionFailureCode.unknown, message: '');

  final CursorConnectionFailureCode code;

  @override
  final String message;
}
