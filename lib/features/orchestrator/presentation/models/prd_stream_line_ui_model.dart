final class PrdStreamLineUiModel {
  const PrdStreamLineUiModel({
    required this.sequence,
    required this.eventType,
    required this.displayText,
    this.requiresUserAction = false,
  });

  final int sequence;
  final String eventType;
  final String displayText;
  final bool requiresUserAction;

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is PrdStreamLineUiModel &&
            other.sequence == sequence &&
            other.eventType == eventType &&
            other.displayText == displayText &&
            other.requiresUserAction == requiresUserAction;
  }

  @override
  int get hashCode =>
      Object.hash(sequence, eventType, displayText, requiresUserAction);
}
