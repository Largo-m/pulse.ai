import 'package:pulse_ai/features/orchestrator/presentation/models/prd_review_load_status.dart';

final class PrdReviewState {
  const PrdReviewState({
    this.loadStatus = PrdReviewLoadStatus.idle,
    this.savedMarkdown = '',
    this.isDirty = false,
    this.isSaving = false,
    this.isApproving = false,
    this.isRejecting = false,
    this.showsUserEditedBadge = false,
    this.repoPathHeader,
    this.branchNameHeader,
    this.sourceRunId,
    this.isApproveBlocked = false,
    this.approveBlockedMessageKey,
    this.mustConfirmOverwrite = false,
    this.pendingOverwriteMarkdown,
    this.failureMessageKey,
    this.isApproved = false,
  });

  final PrdReviewLoadStatus loadStatus;
  final String savedMarkdown;
  final bool isDirty;
  final bool isSaving;
  final bool isApproving;
  final bool isRejecting;
  final bool showsUserEditedBadge;
  final String? repoPathHeader;
  final String? branchNameHeader;
  final String? sourceRunId;
  final bool isApproveBlocked;
  final String? approveBlockedMessageKey;
  final bool mustConfirmOverwrite;
  final String? pendingOverwriteMarkdown;
  final String? failureMessageKey;
  final bool isApproved;

  bool get isEditable => loadStatus == PrdReviewLoadStatus.ready && !isApproved;

  bool get canSave => isEditable && isDirty && !isSaving;

  bool get canApprove =>
      isEditable && !isApproving && !isApproveBlocked && !mustConfirmOverwrite;

  bool get canReject =>
      isEditable &&
      !isRejecting &&
      sourceRunId != null &&
      !mustConfirmOverwrite;

  PrdReviewState copyWith({
    PrdReviewLoadStatus? loadStatus,
    String? savedMarkdown,
    bool? isDirty,
    bool? isSaving,
    bool? isApproving,
    bool? isRejecting,
    bool? showsUserEditedBadge,
    String? repoPathHeader,
    String? branchNameHeader,
    String? sourceRunId,
    bool? isApproveBlocked,
    String? approveBlockedMessageKey,
    bool clearApproveBlockedMessageKey = false,
    bool? mustConfirmOverwrite,
    String? pendingOverwriteMarkdown,
    bool clearPendingOverwriteMarkdown = false,
    String? failureMessageKey,
    bool clearFailureMessageKey = false,
    bool? isApproved,
  }) {
    return PrdReviewState(
      loadStatus: loadStatus ?? this.loadStatus,
      savedMarkdown: savedMarkdown ?? this.savedMarkdown,
      isDirty: isDirty ?? this.isDirty,
      isSaving: isSaving ?? this.isSaving,
      isApproving: isApproving ?? this.isApproving,
      isRejecting: isRejecting ?? this.isRejecting,
      showsUserEditedBadge: showsUserEditedBadge ?? this.showsUserEditedBadge,
      repoPathHeader: repoPathHeader ?? this.repoPathHeader,
      branchNameHeader: branchNameHeader ?? this.branchNameHeader,
      sourceRunId: sourceRunId ?? this.sourceRunId,
      isApproveBlocked: isApproveBlocked ?? this.isApproveBlocked,
      approveBlockedMessageKey: clearApproveBlockedMessageKey
          ? null
          : (approveBlockedMessageKey ?? this.approveBlockedMessageKey),
      mustConfirmOverwrite: mustConfirmOverwrite ?? this.mustConfirmOverwrite,
      pendingOverwriteMarkdown: clearPendingOverwriteMarkdown
          ? null
          : (pendingOverwriteMarkdown ?? this.pendingOverwriteMarkdown),
      failureMessageKey: clearFailureMessageKey
          ? null
          : (failureMessageKey ?? this.failureMessageKey),
      isApproved: isApproved ?? this.isApproved,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdReviewState &&
            other.loadStatus == loadStatus &&
            other.savedMarkdown == savedMarkdown &&
            other.isDirty == isDirty &&
            other.isSaving == isSaving &&
            other.isApproving == isApproving &&
            other.isRejecting == isRejecting &&
            other.showsUserEditedBadge == showsUserEditedBadge &&
            other.repoPathHeader == repoPathHeader &&
            other.branchNameHeader == branchNameHeader &&
            other.sourceRunId == sourceRunId &&
            other.isApproveBlocked == isApproveBlocked &&
            other.approveBlockedMessageKey == approveBlockedMessageKey &&
            other.mustConfirmOverwrite == mustConfirmOverwrite &&
            other.pendingOverwriteMarkdown == pendingOverwriteMarkdown &&
            other.failureMessageKey == failureMessageKey &&
            other.isApproved == isApproved;
  }

  @override
  int get hashCode => Object.hash(
    loadStatus,
    savedMarkdown,
    isDirty,
    isSaving,
    isApproving,
    isRejecting,
    showsUserEditedBadge,
    repoPathHeader,
    branchNameHeader,
    sourceRunId,
    isApproveBlocked,
    approveBlockedMessageKey,
    mustConfirmOverwrite,
    pendingOverwriteMarkdown,
    failureMessageKey,
    isApproved,
  );

  @override
  String toString() =>
      'PrdReviewState(loadStatus: $loadStatus, isDirty: $isDirty, '
      'mustConfirmOverwrite: $mustConfirmOverwrite, isApproved: $isApproved)';
}
