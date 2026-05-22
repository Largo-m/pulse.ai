import 'dart:async';

import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/core/error/prd_run_persistence_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status_extensions.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/restore_prd_session_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/restore_prd_session_result.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_key.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_completion_output_source.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/append_stream_event_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/cancel_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/complete_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/fail_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/reconcile_prd_run_status_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/restore_last_finalized_prd_session_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_session_view_mode.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_event_mapper.dart';

final class PrdWorkflowCubit extends Cubit<PrdWorkflowState> {
  PrdWorkflowCubit({
    required StartPrdAgentRunUseCase startPrdAgentRunUseCase,
    required AppendStreamEventUseCase appendStreamEventUseCase,
    required CompletePrdAgentRunUseCase completePrdAgentRunUseCase,
    required CancelPrdAgentRunUseCase cancelPrdAgentRunUseCase,
    required FailPrdAgentRunUseCase failPrdAgentRunUseCase,
    required RestoreLastFinalizedPrdSessionUseCase
    restoreLastFinalizedPrdSessionUseCase,
    required ReconcilePrdRunStatusUseCase reconcilePrdRunStatusUseCase,
    required PrdRunRepository prdRunRepository,
    required CursorPrdAgentService cursorPrdAgentService,
    required PrdRunCompletionOutputSource completionOutputSource,
    PrdStreamEventMapper? streamEventMapper,
  }) : _startPrdAgentRunUseCase = startPrdAgentRunUseCase,
       _appendStreamEventUseCase = appendStreamEventUseCase,
       _completePrdAgentRunUseCase = completePrdAgentRunUseCase,
       _cancelPrdAgentRunUseCase = cancelPrdAgentRunUseCase,
       _failPrdAgentRunUseCase = failPrdAgentRunUseCase,
       _restoreLastFinalizedPrdSessionUseCase =
           restoreLastFinalizedPrdSessionUseCase,
       _reconcilePrdRunStatusUseCase = reconcilePrdRunStatusUseCase,
       _prdRunRepository = prdRunRepository,
       _cursorPrdAgentService = cursorPrdAgentService,
       _completionOutputSource = completionOutputSource,
       _streamEventMapper = streamEventMapper ?? const PrdStreamEventMapper(),
       super(const PrdWorkflowState());

  final StartPrdAgentRunUseCase _startPrdAgentRunUseCase;
  final AppendStreamEventUseCase _appendStreamEventUseCase;
  final CompletePrdAgentRunUseCase _completePrdAgentRunUseCase;
  final CancelPrdAgentRunUseCase _cancelPrdAgentRunUseCase;
  final FailPrdAgentRunUseCase _failPrdAgentRunUseCase;
  final RestoreLastFinalizedPrdSessionUseCase
  _restoreLastFinalizedPrdSessionUseCase;
  final ReconcilePrdRunStatusUseCase _reconcilePrdRunStatusUseCase;
  final PrdRunRepository _prdRunRepository;
  final CursorPrdAgentService _cursorPrdAgentService;
  final PrdRunCompletionOutputSource _completionOutputSource;
  final PrdStreamEventMapper _streamEventMapper;

  String? _projectId;
  String? _slug;
  String? _repoPath;
  String? _branchName;
  WorkflowEntity? _boundWorkflow;
  StreamSubscription<PrdStreamEvent>? _streamSubscription;
  bool _terminalRunHandled = false;

  Future<void> bindWorkflow({
    required WorkflowEntity workflow,
    required String repoPath,
  }) async {
    _projectId = workflow.projectId;
    _slug = workflow.slug;
    _repoPath = repoPath;
    _branchName = workflow.branchName;
    _boundWorkflow = workflow;

    emit(
      PrdWorkflowState(
        phaseStatus: _phaseStatusFromWorkflow(workflow.prdPhaseStatus),
      ),
    );

    await _hydrateSession(workflow: workflow);
  }

  Future<void> retrySessionRestore() async {
    final WorkflowEntity? workflow = _boundWorkflow;
    if (workflow == null) {
      return;
    }

    emit(
      state.copyWith(
        clearFailureMessageKey: true,
        sessionViewMode: PrdSessionViewMode.empty,
      ),
    );
    await _hydrateSession(workflow: workflow);
  }

  Future<void> _hydrateSession({required WorkflowEntity workflow}) async {
    final String workflowKey = WorkflowKey.compose(
      projectId: workflow.projectId,
      slug: workflow.slug,
    );

    final Either<Failure, List<PrdRunEntity>> runsResult =
        await _prdRunRepository.listRunsForWorkflow(workflowKey);
    if (isClosed) {
      return;
    }

    if (runsResult.isLeft()) {
      emit(
        state.copyWith(
          sessionViewMode: PrdSessionViewMode.restoreFailed,
          failureMessageKey: _failureMessageKey(
            runsResult.getLeft().toNullable()!,
          ),
        ),
      );
      return;
    }

    final List<PrdRunEntity> runs = runsResult.getRight().toNullable()!;
    if (runs.isNotEmpty) {
      final PrdRunEntity latestRun = runs.first;
      if (!latestRun.status.isTerminal) {
        final String? cloudRunId = latestRun.cloudRunId;
        if (cloudRunId != null && cloudRunId.isNotEmpty) {
          await _reconcilePrdRunStatusUseCase(latestRun);
        }
      }
    }

    if (isClosed) {
      return;
    }

    final Either<Failure, RestorePrdSessionResult> restoreResult =
        await _restoreLastFinalizedPrdSessionUseCase(
          RestorePrdSessionRequest(
            workflowKey: workflowKey,
            workflowDirective: workflow.directive,
            workflow: workflow,
          ),
        );

    if (isClosed) {
      return;
    }

    if (restoreResult.isLeft()) {
      emit(
        state.copyWith(
          sessionViewMode: PrdSessionViewMode.restoreFailed,
          failureMessageKey: _failureMessageKey(
            restoreResult.getLeft().toNullable()!,
          ),
          streamLines: const <PrdStreamLineUiModel>[],
          clearRestoredRunId: true,
          clearRestoredConversationMessages: true,
        ),
      );
      return;
    }

    final RestorePrdSessionResult result = restoreResult
        .getRight()
        .toNullable()!;
    switch (result.outcome) {
      case RestorePrdSessionOutcome.empty:
        emit(
          state.copyWith(
            sessionViewMode: PrdSessionViewMode.empty,
            streamLines: const <PrdStreamLineUiModel>[],
            clearRestoredRunId: true,
            clearRestoredConversationMessages: true,
            clearFailureMessageKey: true,
          ),
        );
      case RestorePrdSessionOutcome.inProgressOnly:
        emit(
          state.copyWith(
            sessionViewMode: PrdSessionViewMode.inProgressOnly,
            streamLines: const <PrdStreamLineUiModel>[],
            clearRestoredRunId: true,
            clearRestoredConversationMessages: true,
            clearFailureMessageKey: true,
          ),
        );
      case RestorePrdSessionOutcome.restored:
        final snapshot = result.snapshot!;
        emit(
          state.copyWith(
            sessionViewMode: PrdSessionViewMode.restored,
            streamLines: snapshot.terminalLines,
            restoredConversationMessages: snapshot.conversationMessages,
            restoredRunId: snapshot.runId,
            clearFailureMessageKey: true,
          ),
        );
    }
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

    final bool preserveRestoredSnapshot = state.hasRestoredSnapshot;
    final PrdSessionViewMode nextSessionMode = preserveRestoredSnapshot
        ? PrdSessionViewMode.restoredWithActiveRun
        : state.sessionViewMode;

    emit(
      state.copyWith(
        isStarting: true,
        phaseStatus: PrdWorkflowPhaseUiStatus.running,
        sessionViewMode: nextSessionMode,
        streamLines: preserveRestoredSnapshot
            ? state.streamLines
            : const <PrdStreamLineUiModel>[],
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
          sessionViewMode: preserveRestoredSnapshot
              ? PrdSessionViewMode.restored
              : state.sessionViewMode,
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

    if (state.sessionViewMode == PrdSessionViewMode.restoredWithActiveRun) {
      if (_streamEventMapper.isTerminalStreamEvent(
        eventType: event.eventType,
        payloadSummary: event.payloadSummary,
      )) {
        await _completeActiveRun(runId: runId);
      }
      return;
    }

    final bool lineRequiresUserAction = _streamEventMapper
        .eventRequiresUserAction(event.payloadSummary);
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

    if (_streamEventMapper.isTerminalStreamEvent(
      eventType: event.eventType,
      payloadSummary: event.payloadSummary,
    )) {
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

    final PrdSessionViewMode sessionModeAfterComplete =
        state.sessionViewMode == PrdSessionViewMode.restoredWithActiveRun
        ? PrdSessionViewMode.restored
        : state.sessionViewMode;

    emit(
      state.copyWith(
        phaseStatus: PrdWorkflowPhaseUiStatus.pendingApproval,
        sessionViewMode: sessionModeAfterComplete,
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
          sessionViewMode:
              state.sessionViewMode == PrdSessionViewMode.restoredWithActiveRun
              ? PrdSessionViewMode.restored
              : state.sessionViewMode,
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
        sessionViewMode:
            state.sessionViewMode == PrdSessionViewMode.restoredWithActiveRun
            ? PrdSessionViewMode.restored
            : state.sessionViewMode,
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
    final PrdStreamLineUiModel line = _streamEventMapper.mapLiveEventToLine(
      event,
    );
    final PrdStreamLineUiModel bufferedLine = PrdStreamLineUiModel(
      sequence: line.sequence,
      eventType: line.eventType,
      displayText: line.displayText,
      requiresUserAction: requiresUserAction,
    );
    final List<PrdStreamLineUiModel> next = <PrdStreamLineUiModel>[
      ...current,
      bufferedLine,
    ];
    if (next.length <= PrdStreamBufferPolicy.maxInMemoryEvents) {
      return next;
    }
    return next.sublist(next.length - PrdStreamBufferPolicy.maxInMemoryEvents);
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
    if (failure is PrdRunPersistenceFailure) {
      return OrchestratorStrings.prdWorkflowSessionRestoreFailed;
    }
    return OrchestratorStrings.prdWorkflowSessionRestoreFailed;
  }

  @override
  Future<void> close() async {
    await _disposeStreamSubscription();
    return super.close();
  }
}
