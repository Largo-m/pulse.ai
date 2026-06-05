import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';

final class PrdRunEntity {
  const PrdRunEntity({
    required this.id,
    required this.workflowKey,
    required this.status,
    required this.startedAt,
    this.cloudRunId,
    this.supersedesRunId,
    this.feedback,
    this.endedAt,
  });

  final String id;
  final String workflowKey;
  final String? cloudRunId;
  final PrdRunStatus status;
  final String? supersedesRunId;
  final String? feedback;
  final DateTime startedAt;
  final DateTime? endedAt;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdRunEntity &&
            other.id == id &&
            other.workflowKey == workflowKey &&
            other.cloudRunId == cloudRunId &&
            other.status == status &&
            other.supersedesRunId == supersedesRunId &&
            other.feedback == feedback &&
            other.startedAt == startedAt &&
            other.endedAt == endedAt;
  }

  @override
  int get hashCode => Object.hash(
    id,
    workflowKey,
    cloudRunId,
    status,
    supersedesRunId,
    feedback,
    startedAt,
    endedAt,
  );
}
