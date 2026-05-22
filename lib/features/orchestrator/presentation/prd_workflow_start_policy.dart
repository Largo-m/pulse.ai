import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';

bool showsPrdWorkflowStartButton(PrdWorkflowPhaseUiStatus phaseStatus) {
  return switch (phaseStatus) {
    PrdWorkflowPhaseUiStatus.notStarted ||
    PrdWorkflowPhaseUiStatus.failed ||
    PrdWorkflowPhaseUiStatus.cancelled => true,
    PrdWorkflowPhaseUiStatus.running ||
    PrdWorkflowPhaseUiStatus.pendingApproval ||
    PrdWorkflowPhaseUiStatus.approved => false,
  };
}

bool canInvokePrdWorkflowStart({
  required CursorConnectionStatus connectionStatus,
  required bool isStarting,
  required String? directive,
}) {
  final String trimmed = directive?.trim() ?? '';
  return trimmed.isNotEmpty &&
      !isStarting &&
      connectionStatus == CursorConnectionStatus.connected;
}

String prdWorkflowStartButtonLabel(PrdWorkflowPhaseUiStatus phaseStatus) {
  return switch (phaseStatus) {
    PrdWorkflowPhaseUiStatus.failed || PrdWorkflowPhaseUiStatus.cancelled =>
      OrchestratorStrings.prdWorkflowStartRetryButton,
    PrdWorkflowPhaseUiStatus.notStarted ||
    PrdWorkflowPhaseUiStatus.running ||
    PrdWorkflowPhaseUiStatus.pendingApproval ||
    PrdWorkflowPhaseUiStatus.approved =>
      OrchestratorStrings.prdWorkflowStartButton,
  };
}

String prdWorkflowStartButtonSemantics(PrdWorkflowPhaseUiStatus phaseStatus) {
  return switch (phaseStatus) {
    PrdWorkflowPhaseUiStatus.failed || PrdWorkflowPhaseUiStatus.cancelled =>
      OrchestratorStrings.prdWorkflowStartRetrySemantics,
    PrdWorkflowPhaseUiStatus.notStarted ||
    PrdWorkflowPhaseUiStatus.running ||
    PrdWorkflowPhaseUiStatus.pendingApproval ||
    PrdWorkflowPhaseUiStatus.approved =>
      OrchestratorStrings.prdWorkflowStartSemantics,
  };
}
