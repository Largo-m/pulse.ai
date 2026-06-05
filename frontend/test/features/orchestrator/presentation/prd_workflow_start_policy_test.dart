import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_workflow_start_policy.dart';

void main() {
  group('showsPrdWorkflowStartButton', () {
    test('returns true for notStarted, failed, and cancelled', () {
      expect(
        showsPrdWorkflowStartButton(PrdWorkflowPhaseUiStatus.notStarted),
        isTrue,
      );
      expect(
        showsPrdWorkflowStartButton(PrdWorkflowPhaseUiStatus.failed),
        isTrue,
      );
      expect(
        showsPrdWorkflowStartButton(PrdWorkflowPhaseUiStatus.cancelled),
        isTrue,
      );
    });

    test('returns false for running, pendingApproval, and approved', () {
      expect(
        showsPrdWorkflowStartButton(PrdWorkflowPhaseUiStatus.running),
        isFalse,
      );
      expect(
        showsPrdWorkflowStartButton(PrdWorkflowPhaseUiStatus.pendingApproval),
        isFalse,
      );
      expect(
        showsPrdWorkflowStartButton(PrdWorkflowPhaseUiStatus.approved),
        isFalse,
      );
    });
  });

  group('canInvokePrdWorkflowStart', () {
    test('returns true when connected, not starting, and directive is set', () {
      expect(
        canInvokePrdWorkflowStart(
          connectionStatus: CursorConnectionStatus.connected,
          isStarting: false,
          directive: ' Build PRD ',
        ),
        isTrue,
      );
    });

    test('returns false when connection is not connected', () {
      expect(
        canInvokePrdWorkflowStart(
          connectionStatus: CursorConnectionStatus.disconnected,
          isStarting: false,
          directive: 'directive',
        ),
        isFalse,
      );
    });

    test('returns false when starting or directive is empty', () {
      expect(
        canInvokePrdWorkflowStart(
          connectionStatus: CursorConnectionStatus.connected,
          isStarting: true,
          directive: 'directive',
        ),
        isFalse,
      );
      expect(
        canInvokePrdWorkflowStart(
          connectionStatus: CursorConnectionStatus.connected,
          isStarting: false,
          directive: '   ',
        ),
        isFalse,
      );
      expect(
        canInvokePrdWorkflowStart(
          connectionStatus: CursorConnectionStatus.connected,
          isStarting: false,
          directive: null,
        ),
        isFalse,
      );
    });
  });

  group('prdWorkflowStartButtonLabel', () {
    test('uses retry copy for failed and cancelled', () {
      expect(
        prdWorkflowStartButtonLabel(PrdWorkflowPhaseUiStatus.failed),
        OrchestratorStrings.prdWorkflowStartRetryButton,
      );
      expect(
        prdWorkflowStartButtonLabel(PrdWorkflowPhaseUiStatus.cancelled),
        OrchestratorStrings.prdWorkflowStartRetryButton,
      );
    });

    test('uses start copy for notStarted', () {
      expect(
        prdWorkflowStartButtonLabel(PrdWorkflowPhaseUiStatus.notStarted),
        OrchestratorStrings.prdWorkflowStartButton,
      );
    });
  });
}
