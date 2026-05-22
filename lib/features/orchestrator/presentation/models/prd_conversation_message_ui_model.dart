enum PrdConversationMessageRole { user, agent }

final class PrdConversationMessageUiModel {
  const PrdConversationMessageUiModel({
    required this.role,
    required this.displayText,
    required this.timestamp,
    required this.sequence,
  });

  final PrdConversationMessageRole role;
  final String displayText;
  final DateTime timestamp;
  final int sequence;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdConversationMessageUiModel &&
            other.role == role &&
            other.displayText == displayText &&
            other.timestamp == timestamp &&
            other.sequence == sequence;
  }

  @override
  int get hashCode => Object.hash(role, displayText, timestamp, sequence);
}
