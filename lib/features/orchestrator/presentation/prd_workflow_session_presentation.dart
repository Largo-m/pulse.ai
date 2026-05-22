import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_session_view_mode.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

abstract final class PrdWorkflowFailureMessageKeys {
  static const String restoreFailed = 'restoreFailed';
}

String prdWorkflowFailureMessageForKey(String key) {
  return switch (key) {
    PrdWorkflowFailureMessageKeys.restoreFailed =>
      OrchestratorStrings.prdWorkflowSessionRestoreFailed,
    _ => OrchestratorStrings.prdWorkflowRunFailedGeneric,
  };
}

final class PrdWorkflowSessionPresentation {
  const PrdWorkflowSessionPresentation._();

  static List<PrdStreamLineUiModel> terminalLinesFor(PrdWorkflowState state) {
    return switch (state.sessionViewMode) {
      PrdSessionViewMode.restored ||
      PrdSessionViewMode.restoredWithActiveRun => state.streamLines,
      PrdSessionViewMode.empty ||
      PrdSessionViewMode.inProgressOnly ||
      PrdSessionViewMode.restoreFailed => const <PrdStreamLineUiModel>[],
    };
  }

  static String terminalEmptyMessageFor(PrdWorkflowState state) {
    return switch (state.sessionViewMode) {
      PrdSessionViewMode.inProgressOnly =>
        OrchestratorStrings.prdWorkflowSessionInProgressBody,
      PrdSessionViewMode.empty =>
        OrchestratorStrings.prdWorkflowSessionEmptyBody,
      PrdSessionViewMode.restoreFailed =>
        OrchestratorStrings.prdWorkflowSessionRestoreTerminalHint,
      PrdSessionViewMode.restored || PrdSessionViewMode.restoredWithActiveRun =>
        OrchestratorStrings.prdWorkflowStreamEmpty,
    };
  }

  static bool showsRestoreFailurePanel(PrdWorkflowState state) {
    return state.sessionViewMode == PrdSessionViewMode.restoreFailed;
  }

  static bool showsNewRunOverlayBanner(PrdWorkflowState state) {
    return state.sessionViewMode == PrdSessionViewMode.restoredWithActiveRun;
  }

  static bool showsConversationSection(PrdWorkflowState state) {
    return state.restoredConversationMessages.isNotEmpty;
  }

  static bool showsDirectiveBubble({
    required bool hasDirective,
    required PrdWorkflowState state,
  }) {
    return hasDirective && !showsConversationSection(state);
  }

  static bool showsRunFailureBanner(PrdWorkflowState state) {
    return state.failureMessageKey != null &&
        state.sessionViewMode != PrdSessionViewMode.restoreFailed;
  }

  static String? restoreFailureDisplayMessage(PrdWorkflowState state) {
    if (!showsRestoreFailurePanel(state)) {
      return null;
    }
    final String? key = state.failureMessageKey;
    if (key == null || key.isEmpty) {
      return OrchestratorStrings.prdWorkflowSessionRestoreFailed;
    }
    return key;
  }
}
