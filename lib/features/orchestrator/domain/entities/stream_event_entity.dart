final class StreamEventEntity {
  const StreamEventEntity({
    required this.runId,
    required this.sequence,
    required this.eventType,
    required this.payloadSummary,
    required this.timestamp,
  });

  final String runId;
  final int sequence;
  final String eventType;
  final String payloadSummary;
  final DateTime timestamp;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is StreamEventEntity &&
            other.runId == runId &&
            other.sequence == sequence &&
            other.eventType == eventType &&
            other.payloadSummary == payloadSummary &&
            other.timestamp == timestamp;
  }

  @override
  int get hashCode =>
      Object.hash(runId, sequence, eventType, payloadSummary, timestamp);
}
