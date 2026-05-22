import 'package:flutter/foundation.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/artifact_persistence_failure.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/approve_prd_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/find_prd_approval_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/read_prd_markdown_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/reject_prd_with_feedback_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/run_cursor_connection_preflight_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_prd_draft_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/cursor_connection_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_review_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_review_load_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_artifact_presentation.dart';

final class PrdReviewCubit extends Cubit<PrdReviewState> {
  PrdReviewCubit({
    required ReadPrdMarkdownUseCase readPrdMarkdownUseCase,
    required SavePrdDraftUseCase savePrdDraftUseCase,
    required ApprovePrdUseCase approvePrdUseCase,
    required RejectPrdWithFeedbackUseCase rejectPrdWithFeedbackUseCase,
    required FindPrdApprovalUseCase findPrdApprovalUseCase,
    required RunCursorConnectionPreflightUseCase
    runCursorConnectionPreflightUseCase,
  }) : _readPrdMarkdownUseCase = readPrdMarkdownUseCase,
       _savePrdDraftUseCase = savePrdDraftUseCase,
       _approvePrdUseCase = approvePrdUseCase,
       _rejectPrdWithFeedbackUseCase = rejectPrdWithFeedbackUseCase,
       _findPrdApprovalUseCase = findPrdApprovalUseCase,
       _runCursorConnectionPreflightUseCase =
           runCursorConnectionPreflightUseCase,
       super(const PrdReviewState());

  final ReadPrdMarkdownUseCase _readPrdMarkdownUseCase;
  final SavePrdDraftUseCase _savePrdDraftUseCase;
  final ApprovePrdUseCase _approvePrdUseCase;
  final RejectPrdWithFeedbackUseCase _rejectPrdWithFeedbackUseCase;
  final FindPrdApprovalUseCase _findPrdApprovalUseCase;
  final RunCursorConnectionPreflightUseCase
  _runCursorConnectionPreflightUseCase;

  final ValueNotifier<String> editorText = ValueNotifier<String>('');

  String? _projectId;
  String? _slug;
  String? _repoPath;

  void bindReviewContext({
    required String projectId,
    required String slug,
    required String repoPath,
    required String branchName,
  }) {
    _projectId = projectId;
    _slug = slug;
    _repoPath = repoPath;
    emit(
      state.copyWith(
        repoPathHeader: repoPath,
        branchNameHeader: branchName,
        clearFailureMessageKey: true,
      ),
    );
  }

  void syncConnectionGate(CursorConnectionState connectionState) {
    final bool blocked =
        connectionState.status != CursorConnectionStatus.connected;
    emit(
      state.copyWith(
        isApproveBlocked: blocked,
        approveBlockedMessageKey: blocked
            ? (connectionState.remediationMessage ??
                  OrchestratorStrings.cursorConnectionDisconnectedRemediation)
            : null,
        clearApproveBlockedMessageKey: !blocked,
      ),
    );
  }

  Future<void> loadDraft() async {
    final String? projectId = _projectId;
    final String? slug = _slug;
    if (projectId == null || slug == null) {
      return;
    }

    emit(
      state.copyWith(
        loadStatus: PrdReviewLoadStatus.loading,
        clearFailureMessageKey: true,
      ),
    );

    final PrdApprovalEntity? approval = await _findPrdApprovalUseCase(
      projectId: projectId,
      slug: slug,
    );

    if (approval == null ||
        (approval.status != PrdApprovalStatus.draft &&
            approval.status != PrdApprovalStatus.pendingApproval)) {
      emit(
        state.copyWith(
          loadStatus: PrdReviewLoadStatus.unavailable,
          savedMarkdown: '',
          isDirty: false,
          showsUserEditedBadge: false,
          sourceRunId: approval?.sourceRunId,
        ),
      );
      _setEditorText('');
      return;
    }

    final Either<Failure, String> readResult = await _readPrdMarkdownUseCase(
      projectId: projectId,
      slug: slug,
    );

    if (isClosed) {
      return;
    }

    if (readResult.isLeft()) {
      final Failure failure = readResult.getLeft().toNullable()!;
      if (failure is ArtifactPersistenceFailure &&
          failure.code == ArtifactPersistenceFailureCode.notFound) {
        _applyLoadedContent(
          markdown: '',
          approval: approval,
          missingArtifactMessageKey:
              PrdArtifactFailureMessageKeys.missingArtifact,
        );
        return;
      }
      emit(
        state.copyWith(
          loadStatus: PrdReviewLoadStatus.error,
          failureMessageKey: OrchestratorStrings.prdReviewLoadFailed,
        ),
      );
      return;
    }

    _applyLoadedContent(
      markdown: readResult.getRight().toNullable()!,
      approval: approval,
    );
  }

  void onEditorTextChanged(String text) {
    final bool dirty = text != state.savedMarkdown;
    if (dirty != state.isDirty) {
      emit(state.copyWith(isDirty: dirty));
    }
  }

  Future<void> saveDraft() async {
    final String? projectId = _projectId;
    final String? slug = _slug;
    if (projectId == null || slug == null || !state.canSave) {
      return;
    }

    emit(state.copyWith(isSaving: true, clearFailureMessageKey: true));

    final Either<Failure, void> saveResult = await _savePrdDraftUseCase(
      projectId: projectId,
      slug: slug,
      markdown: editorText.value,
    );

    if (isClosed) {
      return;
    }

    if (saveResult.isLeft()) {
      emit(
        state.copyWith(
          isSaving: false,
          failureMessageKey: _failureMessageKey(
            saveResult.getLeft().toNullable()!,
          ),
        ),
      );
      return;
    }

    final PrdApprovalEntity? approval = await _findPrdApprovalUseCase(
      projectId: projectId,
      slug: slug,
    );

    emit(
      state.copyWith(
        isSaving: false,
        savedMarkdown: editorText.value,
        isDirty: false,
        showsUserEditedBadge: _showsUserEditedBadge(approval),
      ),
    );
  }

  Future<void> approve() async {
    final String? projectId = _projectId;
    final String? slug = _slug;
    if (projectId == null || slug == null || !state.canApprove) {
      return;
    }

    final Either<Failure, void> preflightResult =
        await _runCursorConnectionPreflightUseCase();
    if (isClosed) {
      return;
    }
    if (preflightResult.isLeft()) {
      emit(
        state.copyWith(
          isApproveBlocked: true,
          approveBlockedMessageKey: _connectionFailureMessageKey(
            preflightResult.getLeft().toNullable()!,
          ),
        ),
      );
      return;
    }

    emit(state.copyWith(isApproving: true, clearFailureMessageKey: true));

    if (state.isDirty) {
      final Either<Failure, void> saveResult = await _savePrdDraftUseCase(
        projectId: projectId,
        slug: slug,
        markdown: editorText.value,
      );
      if (isClosed) {
        return;
      }
      if (saveResult.isLeft()) {
        emit(
          state.copyWith(
            isApproving: false,
            failureMessageKey: _failureMessageKey(
              saveResult.getLeft().toNullable()!,
            ),
          ),
        );
        return;
      }
    }

    final Either<Failure, PrdApprovalEntity> approveResult =
        await _approvePrdUseCase(projectId: projectId, slug: slug);

    if (isClosed) {
      return;
    }

    if (approveResult.isLeft()) {
      emit(
        state.copyWith(
          isApproving: false,
          failureMessageKey: _failureMessageKey(
            approveResult.getLeft().toNullable()!,
          ),
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        isApproving: false,
        isApproved: true,
        savedMarkdown: editorText.value,
        isDirty: false,
        loadStatus: PrdReviewLoadStatus.unavailable,
      ),
    );
  }

  Future<void> rejectWithFeedback(String feedback) async {
    final String? projectId = _projectId;
    final String? slug = _slug;
    final String? repoPath = _repoPath;
    final String? rejectedRunId = state.sourceRunId;
    if (projectId == null ||
        slug == null ||
        repoPath == null ||
        rejectedRunId == null ||
        !state.canReject ||
        feedback.trim().isEmpty) {
      return;
    }

    emit(state.copyWith(isRejecting: true, clearFailureMessageKey: true));

    if (state.isDirty) {
      final Either<Failure, void> saveResult = await _savePrdDraftUseCase(
        projectId: projectId,
        slug: slug,
        markdown: editorText.value,
      );
      if (isClosed) {
        return;
      }
      if (saveResult.isLeft()) {
        emit(
          state.copyWith(
            isRejecting: false,
            failureMessageKey: _failureMessageKey(
              saveResult.getLeft().toNullable()!,
            ),
          ),
        );
        return;
      }
      emit(state.copyWith(savedMarkdown: editorText.value, isDirty: false));
    }

    final Either<Failure, PrdRunEntity> rejectResult =
        await _rejectPrdWithFeedbackUseCase(
          projectId: projectId,
          slug: slug,
          repoPath: repoPath,
          rejectedRunId: rejectedRunId,
          feedback: feedback.trim(),
        );

    if (isClosed) {
      return;
    }

    if (rejectResult.isLeft()) {
      emit(
        state.copyWith(
          isRejecting: false,
          failureMessageKey: _failureMessageKey(
            rejectResult.getLeft().toNullable()!,
          ),
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        isRejecting: false,
        loadStatus: PrdReviewLoadStatus.unavailable,
        savedMarkdown: '',
        isDirty: false,
        showsUserEditedBadge: false,
        clearPendingOverwriteMarkdown: true,
        mustConfirmOverwrite: false,
      ),
    );
    _setEditorText('');
  }

  void applyIncomingDraft(String markdown) {
    if (state.isDirty) {
      emit(
        state.copyWith(
          mustConfirmOverwrite: true,
          pendingOverwriteMarkdown: markdown,
        ),
      );
      return;
    }
    _replaceEditorContent(markdown);
  }

  void confirmOverwriteIncomingDraft() {
    final String? pending = state.pendingOverwriteMarkdown;
    if (pending == null) {
      return;
    }
    _replaceEditorContent(pending);
    emit(
      state.copyWith(
        mustConfirmOverwrite: false,
        clearPendingOverwriteMarkdown: true,
      ),
    );
  }

  void cancelOverwriteIncomingDraft() {
    emit(
      state.copyWith(
        mustConfirmOverwrite: false,
        clearPendingOverwriteMarkdown: true,
      ),
    );
  }

  void _applyLoadedContent({
    required String markdown,
    required PrdApprovalEntity approval,
    String? missingArtifactMessageKey,
  }) {
    _replaceEditorContent(markdown);
    emit(
      state.copyWith(
        loadStatus: PrdReviewLoadStatus.ready,
        savedMarkdown: markdown,
        isDirty: false,
        showsUserEditedBadge: _showsUserEditedBadge(approval),
        sourceRunId: approval.sourceRunId,
        isApproved: false,
        mustConfirmOverwrite: false,
        clearPendingOverwriteMarkdown: true,
        failureMessageKey: missingArtifactMessageKey,
        clearFailureMessageKey: missingArtifactMessageKey == null,
      ),
    );
  }

  void _replaceEditorContent(String markdown) {
    _setEditorText(markdown);
    emit(
      state.copyWith(
        savedMarkdown: markdown,
        isDirty: false,
        clearPendingOverwriteMarkdown: true,
        mustConfirmOverwrite: false,
      ),
    );
  }

  void _setEditorText(String text) {
    if (editorText.value != text) {
      editorText.value = text;
    }
  }

  bool _showsUserEditedBadge(PrdApprovalEntity? approval) {
    return approval?.lastEditedAt != null && approval?.sourceRunId != null;
  }

  String _connectionFailureMessageKey(Failure failure) {
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
    return OrchestratorStrings.cursorConnectionDisconnectedRemediation;
  }

  String _failureMessageKey(Failure failure) {
    if (failure is CursorConnectionFailure) {
      return _connectionFailureMessageKey(failure);
    }
    if (failure is PrdRunFailure) {
      return OrchestratorStrings.prdReviewActionFailed;
    }
    return OrchestratorStrings.prdReviewActionFailed;
  }

  @override
  Future<void> close() {
    editorText.dispose();
    return super.close();
  }
}
