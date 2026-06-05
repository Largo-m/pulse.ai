final class CursorCloudRunIdCodec {
  const CursorCloudRunIdCodec._();

  static const String separator = '::';

  static String encode({required String agentId, required String runId}) {
    return '$agentId$separator$runId';
  }

  static ({String agentId, String runId})? decode(String cloudRunId) {
    final int index = cloudRunId.indexOf(separator);
    if (index <= 0 || index >= cloudRunId.length - separator.length) {
      return null;
    }
    return (
      agentId: cloudRunId.substring(0, index),
      runId: cloudRunId.substring(index + separator.length),
    );
  }
}
