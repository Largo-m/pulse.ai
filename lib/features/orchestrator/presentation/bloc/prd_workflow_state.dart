import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_session_view_mode.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';

final class PrdWorkflowState {
  const PrdWorkflowState({
    this.phaseStatus = PrdWorkflowPhaseUiStatus.notStarted,
    this.sessionViewMode = PrdSessionViewMode.empty,
    this.streamLines = const <PrdStreamLineUiModel>[],
    this.liveConversationMessages = const <PrdConversationMessageUiModel>[],
    this.restoredConversationMessages = const <PrdConversationMessageUiModel>[],
    this.restoredRunId,
    this.activeRunId,
    this.failureMessageKey,
    this.requiresUserAction = false,
    this.streamLagMs,
    this.isStarting = false,
    this.isCancelling = false,
  });

  final PrdWorkflowPhaseUiStatus phaseStatus;
  final PrdSessionViewMode sessionViewMode;
  final List<PrdStreamLineUiModel> streamLines;
  final List<PrdConversationMessageUiModel> liveConversationMessages;
  final List<PrdConversationMessageUiModel> restoredConversationMessages;
  final String? restoredRunId;
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

  bool get hasRestoredSnapshot =>
      sessionViewMode == PrdSessionViewMode.restored ||
      sessionViewMode == PrdSessionViewMode.restoredWithActiveRun;

  PrdWorkflowState copyWith({
    PrdWorkflowPhaseUiStatus? phaseStatus,
    PrdSessionViewMode? sessionViewMode,
    List<PrdStreamLineUiModel>? streamLines,
    List<PrdConversationMessageUiModel>? liveConversationMessages,
    List<PrdConversationMessageUiModel>? restoredConversationMessages,
    String? restoredRunId,
    String? activeRunId,
    String? failureMessageKey,
    bool? requiresUserAction,
    int? streamLagMs,
    bool? isStarting,
    bool? isCancelling,
    bool clearActiveRunId = false,
    bool clearFailureMessageKey = false,
    bool clearStreamLagMs = false,
    bool clearRestoredRunId = false,
    bool clearRestoredConversationMessages = false,
    bool clearLiveConversationMessages = false,
  }) {
    return PrdWorkflowState(
      phaseStatus: phaseStatus ?? this.phaseStatus,
      sessionViewMode: sessionViewMode ?? this.sessionViewMode,
      streamLines: streamLines ?? this.streamLines,
      liveConversationMessages: clearLiveConversationMessages
          ? const <PrdConversationMessageUiModel>[]
          : (liveConversationMessages ?? this.liveConversationMessages),
      restoredConversationMessages: clearRestoredConversationMessages
          ? const <PrdConversationMessageUiModel>[]
          : (restoredConversationMessages ?? this.restoredConversationMessages),
      restoredRunId: clearRestoredRunId
          ? null
          : (restoredRunId ?? this.restoredRunId),
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
            other.sessionViewMode == sessionViewMode &&
            _listEquals(other.streamLines, streamLines) &&
            _listEquals(
              other.liveConversationMessages,
              liveConversationMessages,
            ) &&
            _listEquals(
              other.restoredConversationMessages,
              restoredConversationMessages,
            ) &&
            other.restoredRunId == restoredRunId &&
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
    sessionViewMode,
    Object.hashAll(streamLines),
    Object.hashAll(liveConversationMessages),
    Object.hashAll(restoredConversationMessages),
    restoredRunId,
    activeRunId,
    failureMessageKey,
    requiresUserAction,
    streamLagMs,
    isStarting,
    isCancelling,
  );

  @override
  String toString() =>
      'PrdWorkflowState(phaseStatus: $phaseStatus, sessionViewMode: $sessionViewMode, '
      'streamLines: ${streamLines.length}, liveConversation: '
      '${liveConversationMessages.length}, restoredConversation: '
      '${restoredConversationMessages.length}, restoredRunId: $restoredRunId, '
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
