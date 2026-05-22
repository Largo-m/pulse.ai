import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';

void main() {
  group('CursorConnectionState', () {
    test('copyWith replaces remediation message when not clearing', () {
      const CursorConnectionState original = CursorConnectionState(
        remediationMessage: 'antes',
      );

      final CursorConnectionState updated = original.copyWith(
        remediationMessage: 'depois',
      );

      expect(updated.remediationMessage, 'depois');
    });

    test('copyWith updates status and remediation message', () {
      const CursorConnectionState original = CursorConnectionState(
        status: CursorConnectionStatus.checking,
        remediationMessage: 'mensagem',
      );

      final CursorConnectionState updated = original.copyWith(
        status: CursorConnectionStatus.connected,
        clearRemediationMessage: true,
      );

      expect(updated.status, CursorConnectionStatus.connected);
      expect(updated.remediationMessage, isNull);
    });

    test('copyWith updates settings session fields', () {
      const CursorConnectionState original = CursorConnectionState(
        isDraftTestPassed: true,
        settingsOperation: CursorSettingsOperationStatus.testing,
        settingsFeedbackMessageKey: 'feedback',
      );

      final CursorConnectionState updated = original.copyWith(
        isDraftTestPassed: false,
        settingsOperation: CursorSettingsOperationStatus.idle,
        clearSettingsFeedback: true,
      );

      expect(updated.isDraftTestPassed, isFalse);
      expect(updated.settingsOperation, CursorSettingsOperationStatus.idle);
      expect(updated.settingsFeedbackMessageKey, isNull);
    });

    test('equality compares connection and settings fields', () {
      const CursorConnectionState left = CursorConnectionState(
        status: CursorConnectionStatus.failure,
        remediationMessage: 'a',
        isDraftTestPassed: true,
        settingsOperation: CursorSettingsOperationStatus.saving,
        settingsFeedbackMessageKey: 'feedback',
      );
      const CursorConnectionState right = CursorConnectionState(
        status: CursorConnectionStatus.failure,
        remediationMessage: 'a',
        isDraftTestPassed: true,
        settingsOperation: CursorSettingsOperationStatus.saving,
        settingsFeedbackMessageKey: 'feedback',
      );
      const CursorConnectionState different = CursorConnectionState(
        status: CursorConnectionStatus.connected,
      );

      expect(left, right);
      expect(left, isNot(different));
      expect(left.hashCode, right.hashCode);
    });

    test('toString omits secrets and includes status', () {
      const CursorConnectionState state = CursorConnectionState(
        status: CursorConnectionStatus.disconnected,
        remediationMessage: 'Configure a chave',
      );

      expect(state.toString(), contains('disconnected'));
      expect(state.toString(), isNot(contains('sk-live-')));
    });
  });
}
