import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';

final class PrdWorkflowState {
  const PrdWorkflowState({
    this.phaseStatus = PrdWorkflowPhaseUiStatus.notStarted,
    this.streamLines = const <PrdStreamLineUiModel>[],
    this.activeRunId,
    this.failureMessageKey,
    this.requiresUserAction = false,
    this.streamLagMs,
    this.isStarting = false,
    this.isCancelling = false,
  });

  final PrdWorkflowPhaseUiStatus phaseStatus;
  final List<PrdStreamLineUiModel> streamLines;
  final String? activeRunId;
  final String? failureMessageKey;
  final bool requiresUserAction;
  final int? streamLagMs;
  final bool isStarting;
  final bool isCancelling;

  bool get canCancel =>
      phaseStatus == PrdWorkflowPhaseUiStatus.running &&
      activeRunId != null &&
      !isCancelling;

  PrdWorkflowState copyWith({
    PrdWorkflowPhaseUiStatus? phaseStatus,
    List<PrdStreamLineUiModel>? streamLines,
    String? activeRunId,
    String? failureMessageKey,
    bool? requiresUserAction,
    int? streamLagMs,
    bool? isStarting,
    bool? isCancelling,
    bool clearActiveRunId = false,
    bool clearFailureMessageKey = false,
    bool clearStreamLagMs = false,
  }) {
    return PrdWorkflowState(
      phaseStatus: phaseStatus ?? this.phaseStatus,
      streamLines: streamLines ?? this.streamLines,
      activeRunId: clearActiveRunId ? null : (activeRunId ?? this.activeRunId),
      failureMessageKey: clearFailureMessageKey
          ? null
          : (failureMessageKey ?? this.failureMessageKey),
      requiresUserAction: requiresUserAction ?? this.requiresUserAction,
      streamLagMs: clearStreamLagMs ? null : (streamLagMs ?? this.streamLagMs),
      isStarting: isStarting ?? this.isStarting,
      isCancelling: isCancelling ?? this.isCancelling,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdWorkflowState &&
            other.phaseStatus == phaseStatus &&
            _listEquals(other.streamLines, streamLines) &&
            other.activeRunId == activeRunId &&
            other.failureMessageKey == failureMessageKey &&
            other.requiresUserAction == requiresUserAction &&
            other.streamLagMs == streamLagMs &&
            other.isStarting == isStarting &&
            other.isCancelling == isCancelling;
  }

  @override
  int get hashCode => Object.hash(
    phaseStatus,
    Object.hashAll(streamLines),
    activeRunId,
    failureMessageKey,
    requiresUserAction,
    streamLagMs,
    isStarting,
    isCancelling,
  );

  @override
  String toString() =>
      'PrdWorkflowState(phaseStatus: $phaseStatus, streamLines: ${streamLines.length}, '
      'activeRunId: $activeRunId, failureMessageKey: $failureMessageKey, '
      'requiresUserAction: $requiresUserAction, streamLagMs: $streamLagMs, '
      'isStarting: $isStarting, isCancelling: $isCancelling)';
}

bool _listEquals<T>(List<T> a, List<T> b) {
  if (a.length != b.length) {
    return false;
  }
  for (int i = 0; i < a.length; i++) {
    if (a[i] != b[i]) {
      return false;
    }
  }
  return true;
}
