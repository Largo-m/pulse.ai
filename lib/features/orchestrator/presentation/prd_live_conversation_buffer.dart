import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';

abstract final class PrdLiveConversationBuffer {
  const PrdLiveConversationBuffer._();

  static List<PrdConversationMessageUiModel> seedFromRunInput({
    required String directive,
    String? feedback,
    required DateTime timestamp,
  }) {
    final List<PrdConversationMessageUiModel> messages =
        <PrdConversationMessageUiModel>[];
    final String trimmedDirective = directive.trim();
    if (trimmedDirective.isNotEmpty) {
      messages.add(
        PrdConversationMessageUiModel(
          role: PrdConversationMessageRole.user,
          displayText: trimmedDirective,
          timestamp: timestamp,
          sequence: 0,
        ),
      );
    }
    final String? trimmedFeedback = feedback?.trim();
    if (trimmedFeedback != null && trimmedFeedback.isNotEmpty) {
      messages.add(
        PrdConversationMessageUiModel(
          role: PrdConversationMessageRole.user,
          displayText: trimmedFeedback,
          timestamp: timestamp,
          sequence: messages.length,
        ),
      );
    }
    return List<PrdConversationMessageUiModel>.unmodifiable(messages);
  }

  static List<PrdConversationMessageUiModel> appendAgentMessage(
    List<PrdConversationMessageUiModel> current,
    PrdConversationMessageUiModel incoming,
  ) {
    if (current.isEmpty) {
      return <PrdConversationMessageUiModel>[incoming];
    }
    final PrdConversationMessageUiModel last = current.last;
    if (last.role != PrdConversationMessageRole.agent ||
        incoming.role != PrdConversationMessageRole.agent) {
      return <PrdConversationMessageUiModel>[...current, incoming];
    }
    final String mergedText = _mergeAgentText(
      last.displayText,
      incoming.displayText,
    );
    final PrdConversationMessageUiModel merged = PrdConversationMessageUiModel(
      role: PrdConversationMessageRole.agent,
      displayText: mergedText,
      timestamp: incoming.timestamp,
      sequence: incoming.sequence,
    );
    return <PrdConversationMessageUiModel>[
      ...current.sublist(0, current.length - 1),
      merged,
    ];
  }

  static String _mergeAgentText(String previous, String incoming) {
    if (incoming.startsWith(previous)) {
      return incoming;
    }
    if (previous.startsWith(incoming)) {
      return previous;
    }
    return '$previous$incoming';
  }
}
