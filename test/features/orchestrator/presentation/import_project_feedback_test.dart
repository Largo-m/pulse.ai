import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/features/orchestrator/presentation/import_project_feedback.dart';
import 'package:pulse_ai/features/orchestrator/presentation/import_project_strings.dart';

void main() {
  group('ImportProjectFeedback', () {
    test(
      'resolveFailureMessage returns generic message when failure is null',
      () {
        expect(
          ImportProjectFeedback.resolveFailureMessage(null),
          ImportProjectStrings.importLocalFailureMessage,
        );
      },
    );

    test(
      'resolveFailureMessage returns permission message for sandbox errors',
      () {
        expect(
          ImportProjectFeedback.resolveFailureMessage(
            'com.apple.security.files.user-selected.read-only entitlement missing',
          ),
          ImportProjectStrings.importLocalPermissionFailureMessage,
        );
      },
    );

    test(
      'resolveFailureMessage returns generic message for unknown errors',
      () {
        expect(
          ImportProjectFeedback.resolveFailureMessage('disk full'),
          ImportProjectStrings.importLocalFailureMessage,
        );
      },
    );
  });
}
