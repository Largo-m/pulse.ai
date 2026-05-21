import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/widgets/cursor_connection_banner_policy.dart';

void main() {
  group('CursorConnectionBannerPolicy', () {
    test('shouldShow returns true only when disconnected', () {
      expect(
        CursorConnectionBannerPolicy.shouldShow(
          CursorConnectionStatus.disconnected,
        ),
        isTrue,
      );
      expect(
        CursorConnectionBannerPolicy.shouldShow(
          CursorConnectionStatus.connected,
        ),
        isFalse,
      );
      expect(
        CursorConnectionBannerPolicy.shouldShow(CursorConnectionStatus.failure),
        isFalse,
      );
    });

    test(
      'remediationMessage uses disconnected remediation constant when state has no message',
      () {
        const CursorConnectionState state = CursorConnectionState(
          status: CursorConnectionStatus.disconnected,
        );

        expect(
          CursorConnectionBannerPolicy.remediationMessage(state),
          OrchestratorStrings.cursorConnectionMissingCredentialRemediation,
        );
      },
    );

    test('remediationMessage prefers state remediation when present', () {
      const CursorConnectionState state = CursorConnectionState(
        status: CursorConnectionStatus.disconnected,
        remediationMessage:
            OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
      );

      expect(
        CursorConnectionBannerPolicy.remediationMessage(state),
        OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
      );
    });
  });
}
