import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';

final class PrdSessionSnapshot {
  const PrdSessionSnapshot({
    required this.runId,
    required this.runStatus,
    required this.terminalLines,
    required this.conversationMessages,
  });

  final String runId;
  final PrdRunStatus runStatus;
  final List<PrdStreamLineUiModel> terminalLines;
  final List<PrdConversationMessageUiModel> conversationMessages;
}
