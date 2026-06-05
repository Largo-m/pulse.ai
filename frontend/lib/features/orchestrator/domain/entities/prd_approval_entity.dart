import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';

final class PrdApprovalEntity {
  const PrdApprovalEntity({
    required this.workflowKey,
    required this.status,
    this.approvedAt,
    this.lastEditedAt,
    this.sourceRunId,
  });

  final String workflowKey;
  final PrdApprovalStatus status;
  final DateTime? approvedAt;
  final DateTime? lastEditedAt;
  final String? sourceRunId;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdApprovalEntity &&
            other.workflowKey == workflowKey &&
            other.status == status &&
            other.approvedAt == approvedAt &&
            other.lastEditedAt == lastEditedAt &&
            other.sourceRunId == sourceRunId;
  }

  @override
  int get hashCode =>
      Object.hash(workflowKey, status, approvedAt, lastEditedAt, sourceRunId);
}
