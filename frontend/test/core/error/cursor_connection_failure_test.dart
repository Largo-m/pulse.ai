import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';

void main() {
  group('CursorConnectionFailure', () {
    test('factory constructors expose expected codes', () {
      expect(
        const CursorConnectionFailure.missingCredential().code,
        CursorConnectionFailureCode.missingCredential,
      );
      expect(
        const CursorConnectionFailure.unauthorized().code,
        CursorConnectionFailureCode.unauthorized,
      );
      expect(
        const CursorConnectionFailure.network().code,
        CursorConnectionFailureCode.network,
      );
      expect(
        const CursorConnectionFailure.unknown().code,
        CursorConnectionFailureCode.unknown,
      );
    });
  });
}
