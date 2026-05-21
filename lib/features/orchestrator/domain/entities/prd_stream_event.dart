final class PrdStreamEvent {
  const PrdStreamEvent({
    required this.runId,
    required this.eventType,
    required this.sequence,
    required this.timestamp,
    this.payloadSummary,
  });

  final String runId;
  final String eventType;
  final int sequence;
  final DateTime timestamp;
  final String? payloadSummary;
}
