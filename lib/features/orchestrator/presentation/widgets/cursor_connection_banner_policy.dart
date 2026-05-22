import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

abstract final class CursorConnectionBannerPolicy {
  static bool shouldShow(CursorConnectionStatus status) {
    return status == CursorConnectionStatus.disconnected ||
        status == CursorConnectionStatus.failure;
  }

  static String remediationMessage(CursorConnectionState state) {
    return state.remediationMessage ??
        OrchestratorStrings.cursorConnectionMissingCredentialRemediation;
  }
}
