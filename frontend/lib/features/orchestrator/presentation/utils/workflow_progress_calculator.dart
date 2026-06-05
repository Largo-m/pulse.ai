import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';

int workflowProgressPercent({
  required PrdWorkflowPhaseUiStatus phaseStatus,
  required int streamLineCount,
}) {
  return switch (phaseStatus) {
    PrdWorkflowPhaseUiStatus.notStarted => 0,
    PrdWorkflowPhaseUiStatus.running => _runningProgress(streamLineCount),
    PrdWorkflowPhaseUiStatus.pendingApproval => 100,
    PrdWorkflowPhaseUiStatus.approved => 100,
    PrdWorkflowPhaseUiStatus.failed => _runningProgress(streamLineCount),
    PrdWorkflowPhaseUiStatus.cancelled => _runningProgress(streamLineCount),
  };
}

int _runningProgress(int streamLineCount) {
  if (streamLineCount <= 0) {
    return 12;
  }
  final int scaled = 12 + (streamLineCount * 8);
  return scaled.clamp(12, 95);
}

String workflowProgressLabel(int percent) {
  return '$percent% concluído';
}

String workflowTechspecCompletionLabel(int percent) {
  return '$percent% DE CONCLUSÃO';
}
