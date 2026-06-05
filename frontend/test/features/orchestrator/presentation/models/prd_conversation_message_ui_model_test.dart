import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';

void main() {
  final DateTime timestamp = DateTime.utc(2026, 5, 22);

  test('equality compares role, displayText, timestamp, and sequence', () {
    final PrdConversationMessageUiModel left = PrdConversationMessageUiModel(
      role: PrdConversationMessageRole.user,
      displayText: 'Olá',
      timestamp: timestamp,
      sequence: 1,
    );
    final PrdConversationMessageUiModel same = PrdConversationMessageUiModel(
      role: PrdConversationMessageRole.user,
      displayText: 'Olá',
      timestamp: timestamp,
      sequence: 1,
    );
    final PrdConversationMessageUiModel different =
        PrdConversationMessageUiModel(
          role: PrdConversationMessageRole.agent,
          displayText: 'Olá',
          timestamp: timestamp,
          sequence: 1,
        );

    expect(left, same);
    expect(left.hashCode, same.hashCode);
    expect(left == different, isFalse);
  });
}
