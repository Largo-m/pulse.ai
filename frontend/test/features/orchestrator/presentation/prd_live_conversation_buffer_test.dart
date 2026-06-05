import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_live_conversation_buffer.dart';

void main() {
  group('PrdLiveConversationBuffer', () {
    final DateTime timestamp = DateTime.utc(2026, 5, 22);

    test('seedFromRunInput includes directive and feedback', () {
      final List<PrdConversationMessageUiModel> messages =
          PrdLiveConversationBuffer.seedFromRunInput(
            directive: '  Build PRD  ',
            feedback: ' focus payments ',
            timestamp: timestamp,
          );

      expect(messages, hasLength(2));
      expect(messages.first.displayText, 'Build PRD');
      expect(messages.last.displayText, 'focus payments');
    });

    test('appendAgentMessage merges incremental assistant chunks', () {
      final PrdConversationMessageUiModel first = PrdConversationMessageUiModel(
        role: PrdConversationMessageRole.agent,
        displayText: 'Hello',
        timestamp: timestamp,
        sequence: 1,
      );
      final PrdConversationMessageUiModel second =
          PrdConversationMessageUiModel(
            role: PrdConversationMessageRole.agent,
            displayText: 'Hello world',
            timestamp: timestamp,
            sequence: 2,
          );

      final List<PrdConversationMessageUiModel> merged =
          PrdLiveConversationBuffer.appendAgentMessage(
            <PrdConversationMessageUiModel>[first],
            second,
          );

      expect(merged, hasLength(1));
      expect(merged.single.displayText, 'Hello world');
    });
  });
}
