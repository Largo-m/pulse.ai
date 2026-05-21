import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_completion_output_source.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/append_stream_event_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/cancel_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/complete_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/fail_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';

final class PrdWorkflowCubit extends Cubit<PrdWorkflowState> {
  PrdWorkflowCubit({
    required StartPrdAgentRunUseCase startPrdAgentRunUseCase,
    required AppendStreamEventUseCase appendStreamEventUseCase,
    required CompletePrdAgentRunUseCase completePrdAgentRunUseCase,
    required CancelPrdAgentRunUseCase cancelPrdAgentRunUseCase,
    required FailPrdAgentRunUseCase failPrdAgentRunUseCase,
    required CursorPrdAgentService cursorPrdAgentService,
    required PrdRunCompletionOutputSource completionOutputSource,
  }) : _startPrdAgentRunUseCase = startPrdAgentRunUseCase,
       _appendStreamEventUseCase = appendStreamEventUseCase,
       _completePrdAgentRunUseCase = completePrdAgentRunUseCase,
       _cancelPrdAgentRunUseCase = cancelPrdAgentRunUseCase,
       _failPrdAgentRunUseCase = failPrdAgentRunUseCase,
       _cursorPrdAgentService = cursorPrdAgentService,
       _completionOutputSource = completionOutputSource,
       super(const PrdWorkflowState());

  final StartPrdAgentRunUseCase _startPrdAgentRunUseCase;
  final AppendStreamEventUseCase _appendStreamEventUseCase;
  final CompletePrdAgentRunUseCase _completePrdAgentRunUseCase;
  final CancelPrdAgentRunUseCase _cancelPrdAgentRunUseCase;
  final FailPrdAgentRunUseCase _failPrdAgentRunUseCase;
  final CursorPrdAgentService _cursorPrdAgentService;
  final PrdRunCompletionOutputSource _completionOutputSource;

  String? _projectId;
  String? _slug;
  String? _repoPath;
  String? _branchName;
  StreamSubscription<PrdStreamEvent>? _streamSubscription;
  bool _terminalRunHandled = false;

  void bindWorkflow({
    required WorkflowEntity workflow,
    required String repoPath,
  }) {
    _projectId = workflow.projectId;
    _slug = workflow.slug;
    _repoPath = repoPath;
    _branchName = workflow.branchName;
    emit(
      PrdWorkflowState(
        phaseStatus: _phaseStatusFromWorkflow(workflow.prdPhaseStatus),
      ),
    );
  }

  Future<void> startRun({
    required String directive,
    String? feedback,
    String? supersedesRunId,
  }) async {
    final String? projectId = _projectId;
    final String? slug = _slug;
    final String? repoPath = _repoPath;
    final String? branchName = _branchName;
    if (projectId == null ||
        slug == null ||
        repoPath == null ||
        branchName == null) {
      return;
    }

    await _disposeStreamSubscription();
    _terminalRunHandled = false;

    emit(
      state.copyWith(
        isStarting: true,
        phaseStatus: PrdWorkflowPhaseUiStatus.running,
        streamLines: const <PrdStreamLineUiModel>[],
        requiresUserAction: false,
        clearFailureMessageKey: true,
        clearActiveRunId: true,
        clearStreamLagMs: true,
      ),
    );

    final Either<Failure, PrdRunEntity> startResult =
        await _startPrdAgentRunUseCase(
          PrdRunRequest(
            projectId: projectId,
            slug: slug,
            repoPath: repoPath,
            branchName: branchName,
            directive: directive,
            feedback: feedback,
            supersedesRunId: supersedesRunId,
          ),
        );

    if (isClosed) {
      return;
    }

    if (startResult.isLeft()) {
      emit(
        state.copyWith(
          isStarting: false,
          phaseStatus: PrdWorkflowPhaseUiStatus.failed,
          failureMessageKey: _failureMessageKey(
            startResult.getLeft().toNullable()!,
          ),
        ),
      );
      return;
    }

    final PrdRunEntity run = startResult.getRight().toNullable()!;
    emit(
      state.copyWith(
        isStarting: false,
        phaseStatus: PrdWorkflowPhaseUiStatus.running,
        activeRunId: run.id,
      ),
    );
    await _subscribeToRun(run);
  }

  Future<void> cancelActiveRun() async {
    final String? runId = state.activeRunId;
    final String? projectId = _projectId;
    final String? slug = _slug;
    if (runId == null || projectId == null || slug == null) {
      return;
    }

    emit(state.copyWith(isCancelling: true));
    await _disposeStreamSubscription();
    _terminalRunHandled = true;

    final Either<Failure, PrdRunEntity> cancelResult =
        await _cancelPrdAgentRunUseCase(
          runId: runId,
          projectId: projectId,
          slug: slug,
        );

    if (isClosed) {
      return;
    }

    if (cancelResult.isLeft()) {
      emit(
        state.copyWith(
          isCancelling: false,
          phaseStatus: PrdWorkflowPhaseUiStatus.failed,
          failureMessageKey: _failureMessageKey(
            cancelResult.getLeft().toNullable()!,
          ),
          clearActiveRunId: true,
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        isCancelling: false,
        phaseStatus: PrdWorkflowPhaseUiStatus.cancelled,
        clearActiveRunId: true,
        requiresUserAction: false,
      ),
    );
  }

  Future<void> _subscribeToRun(PrdRunEntity run) async {
    final String? cloudRunId = run.cloudRunId;
    if (cloudRunId == null || cloudRunId.isEmpty) {
      await _handleRunFailed(run.id);
      return;
    }

    _streamSubscription = _cursorPrdAgentService
        .watchRun(cloudRunId)
        .listen(
          (PrdStreamEvent event) {
            unawaited(_onStreamEvent(runId: run.id, event: event));
          },
          onError: (_) {
            unawaited(_handleRunFailed(run.id));
          },
        );
  }

  Future<void> _onStreamEvent({
    required String runId,
    required PrdStreamEvent event,
  }) async {
    if (isClosed || _terminalRunHandled) {
      return;
    }

    final String? projectId = _projectId;
    final String? slug = _slug;
    if (projectId == null || slug == null) {
      return;
    }

    final DateTime receivedAt = DateTime.now().toUtc();
    final int streamLagMs = receivedAt
        .difference(event.timestamp)
        .inMilliseconds
        .clamp(0, 1 << 31);

    await _appendStreamEventUseCase(
      runId: runId,
      projectId: projectId,
      slug: slug,
      event: event,
    );

    if (isClosed || _terminalRunHandled) {
      return;
    }

    if (event.eventType == 'error') {
      await _handleRunFailed(runId);
      return;
    }

    final bool lineRequiresUserAction = _eventRequiresUserAction(event);
    final List<PrdStreamLineUiModel> nextLines = _appendBufferedLine(
      state.streamLines,
      event,
      lineRequiresUserAction,
    );

    emit(
      state.copyWith(
        streamLines: nextLines,
        requiresUserAction: state.requiresUserAction || lineRequiresUserAction,
        streamLagMs: streamLagMs,
      ),
    );

    if (_isTerminalStreamEvent(event)) {
      await _completeActiveRun(runId: runId);
    }
  }

  Future<void> _completeActiveRun({required String runId}) async {
    if (_terminalRunHandled) {
      return;
    }
    _terminalRunHandled = true;
    await _disposeStreamSubscription();

    final String? projectId = _projectId;
    final String? slug = _slug;
    if (projectId == null || slug == null) {
      return;
    }

    final output = await _completionOutputSource.resolve(
      runId: runId,
      projectId: projectId,
      slug: slug,
    );

    final Either<Failure, PrdRunEntity> completeResult =
        await _completePrdAgentRunUseCase(
          runId: runId,
          projectId: projectId,
          slug: slug,
          output: output,
        );

    if (isClosed) {
      return;
    }

    if (completeResult.isLeft()) {
      emit(
        state.copyWith(
          phaseStatus: PrdWorkflowPhaseUiStatus.failed,
          failureMessageKey: _failureMessageKey(
            completeResult.getLeft().toNullable()!,
          ),
          clearActiveRunId: true,
          requiresUserAction: false,
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        phaseStatus: PrdWorkflowPhaseUiStatus.pendingApproval,
        clearActiveRunId: true,
        requiresUserAction: false,
      ),
    );
  }

  Future<void> _handleRunFailed(String runId) async {
    if (_terminalRunHandled) {
      return;
    }
    _terminalRunHandled = true;
    await _disposeStreamSubscription();

    final String? projectId = _projectId;
    final String? slug = _slug;
    if (projectId == null || slug == null) {
      emit(
        state.copyWith(
          phaseStatus: PrdWorkflowPhaseUiStatus.failed,
          failureMessageKey: OrchestratorStrings.prdWorkflowRunFailedGeneric,
          clearActiveRunId: true,
          requiresUserAction: false,
        ),
      );
      return;
    }

    await _failPrdAgentRunUseCase(
      runId: runId,
      projectId: projectId,
      slug: slug,
    );

    if (isClosed) {
      return;
    }

    emit(
      state.copyWith(
        phaseStatus: PrdWorkflowPhaseUiStatus.failed,
        failureMessageKey: OrchestratorStrings.prdWorkflowRunFailedGeneric,
        clearActiveRunId: true,
        requiresUserAction: false,
      ),
    );
  }

  Future<void> _disposeStreamSubscription() async {
    await _streamSubscription?.cancel();
    _streamSubscription = null;
  }

  List<PrdStreamLineUiModel> _appendBufferedLine(
    List<PrdStreamLineUiModel> current,
    PrdStreamEvent event,
    bool requiresUserAction,
  ) {
    final PrdStreamLineUiModel line = PrdStreamLineUiModel(
      sequence: event.sequence,
      eventType: event.eventType,
      displayText: _displayTextForEvent(event),
      requiresUserAction: requiresUserAction,
    );
    final List<PrdStreamLineUiModel> next = <PrdStreamLineUiModel>[
      ...current,
      line,
    ];
    if (next.length <= PrdStreamBufferPolicy.maxInMemoryEvents) {
      return next;
    }
    return next.sublist(next.length - PrdStreamBufferPolicy.maxInMemoryEvents);
  }

  String _displayTextForEvent(PrdStreamEvent event) {
    final String? summary = event.payloadSummary;
    if (summary != null && summary.isNotEmpty) {
      return summary;
    }
    return switch (event.eventType) {
      'status' => OrchestratorStrings.prdWorkflowStreamEventStatus,
      'assistant' => OrchestratorStrings.prdWorkflowStreamEventAssistant,
      'thinking' => OrchestratorStrings.prdWorkflowStreamEventThinking,
      'tool_call' => OrchestratorStrings.prdWorkflowStreamEventToolCall,
      'done' => OrchestratorStrings.prdWorkflowStreamEventDone,
      'heartbeat' => OrchestratorStrings.prdWorkflowStreamEventHeartbeat,
      _ => OrchestratorStrings.prdWorkflowStreamEventGeneric,
    };
  }

  bool _isTerminalStreamEvent(PrdStreamEvent event) {
    if (event.eventType == 'done') {
      return true;
    }
    if (event.eventType == 'result') {
      final String? summary = event.payloadSummary;
      return summary != null && summary.toUpperCase().contains('FINISHED');
    }
    return false;
  }

  bool _eventRequiresUserAction(PrdStreamEvent event) {
    final String? summary = event.payloadSummary;
    if (summary == null || summary.isEmpty) {
      return false;
    }
    final String normalized = summary.toUpperCase();
    return normalized.contains('USER_ACTION') ||
        normalized.contains('AWAITING') ||
        normalized.contains('INPUT_REQUIRED');
  }

  PrdWorkflowPhaseUiStatus _phaseStatusFromWorkflow(PrdPhaseStatus status) {
    return switch (status) {
      PrdPhaseStatus.draft => PrdWorkflowPhaseUiStatus.notStarted,
      PrdPhaseStatus.running => PrdWorkflowPhaseUiStatus.running,
      PrdPhaseStatus.pendingApproval =>
        PrdWorkflowPhaseUiStatus.pendingApproval,
      PrdPhaseStatus.approved => PrdWorkflowPhaseUiStatus.approved,
    };
  }

  String _failureMessageKey(Failure failure) {
    if (failure is CursorConnectionFailure) {
      return switch (failure.code) {
        CursorConnectionFailureCode.missingCredential =>
          OrchestratorStrings.cursorConnectionMissingCredentialRemediation,
        CursorConnectionFailureCode.unauthorized =>
          OrchestratorStrings.cursorConnectionUnauthorizedRemediation,
        CursorConnectionFailureCode.network ||
        CursorConnectionFailureCode.unknown =>
          OrchestratorStrings.cursorConnectionDisconnectedRemediation,
      };
    }
    if (failure is PrdRunFailure) {
      return switch (failure.code) {
        PrdRunFailureCode.streamUnavailable =>
          OrchestratorStrings.prdWorkflowStreamUnavailable,
        PrdRunFailureCode.cloudRunFailed ||
        PrdRunFailureCode.cloudRunNotFound ||
        PrdRunFailureCode.runNotActive ||
        PrdRunFailureCode.cancelled =>
          OrchestratorStrings.prdWorkflowRunFailedGeneric,
        PrdRunFailureCode.projectNotFound ||
        PrdRunFailureCode.branchInvalid ||
        PrdRunFailureCode.gitContextUnavailable ||
        PrdRunFailureCode.workflowNotFound =>
          OrchestratorStrings.prdWorkflowRunFailedGeneric,
      };
    }
    return OrchestratorStrings.prdWorkflowRunFailedGeneric;
  }

  @override
  Future<void> close() async {
    await _disposeStreamSubscription();
    return super.close();
  }
}
