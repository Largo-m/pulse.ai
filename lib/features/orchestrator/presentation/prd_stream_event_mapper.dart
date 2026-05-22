import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';

final class PrdStreamEventMapperResult {
  const PrdStreamEventMapperResult({
    required this.terminalLines,
    required this.conversationMessages,
  });

  final List<PrdStreamLineUiModel> terminalLines;
  final List<PrdConversationMessageUiModel> conversationMessages;
}

/// Maps persisted stream events and live [PrdStreamEvent] values into terminal
/// lines and conversation bubbles with identical rules (ADR-002, ADR-004).
///
/// **Restore (task 03):** Pass events ascending by `sequence` from
/// [PrdRunRepository.listStreamEvents]. Supply [workflowDirective] and
/// [runFeedback] from the workflow/run being restored. User bubbles precede
/// agent bubbles; [runFeedback] is appended after stream-derived messages.
///
/// **Live (task 04):** Use [mapLiveEventToLine] per SSE event; conversation
/// derivation for live runs uses the same inclusion rules via
/// [conversationMessageFromLiveEvent] when wiring the cubit.
final class PrdStreamEventMapper {
  const PrdStreamEventMapper();

  static const int _workflowDirectiveConversationSequence = 0;

  PrdStreamEventMapperResult mapPersistedEvents({
    required List<StreamEventEntity> events,
    String? workflowDirective,
    String? runFeedback,
  }) {
    final List<StreamEventEntity> capped = capPersistedEvents(events);
    final List<PrdStreamLineUiModel> terminalLines = capped
        .map(mapPersistedEventToLine)
        .toList(growable: false);
    final List<PrdConversationMessageUiModel> conversation =
        <PrdConversationMessageUiModel>[];

    final String? directive = _nonEmpty(workflowDirective);
    if (directive != null) {
      conversation.add(
        _userConversationMessage(
          displayText: directive,
          sequence: _workflowDirectiveConversationSequence,
          timestamp: _timestampForUserMessage(capped, preferFirst: true),
        ),
      );
    }

    for (final StreamEventEntity event in capped) {
      final PrdConversationMessageUiModel? agentMessage =
          conversationMessageFromPersistedEvent(event);
      if (agentMessage != null) {
        conversation.add(agentMessage);
      }
    }

    final String? feedback = _nonEmpty(runFeedback);
    if (feedback != null) {
      conversation.add(
        _userConversationMessage(
          displayText: feedback,
          sequence: _runFeedbackConversationSequence(capped),
          timestamp: _timestampForUserMessage(capped, preferFirst: false),
        ),
      );
    }

    return PrdStreamEventMapperResult(
      terminalLines: terminalLines,
      conversationMessages: conversation,
    );
  }

  List<StreamEventEntity> capPersistedEvents(List<StreamEventEntity> events) {
    if (events.length <= PrdStreamBufferPolicy.maxInMemoryEvents) {
      return List<StreamEventEntity>.unmodifiable(events);
    }
    return List<StreamEventEntity>.unmodifiable(
      events.sublist(events.length - PrdStreamBufferPolicy.maxInMemoryEvents),
    );
  }

  PrdStreamLineUiModel mapPersistedEventToLine(StreamEventEntity event) {
    return PrdStreamLineUiModel(
      sequence: event.sequence,
      eventType: event.eventType,
      displayText: displayTextForPersistedEvent(event),
      requiresUserAction: eventRequiresUserAction(event.payloadSummary),
    );
  }

  PrdStreamLineUiModel mapLiveEventToLine(PrdStreamEvent event) {
    return PrdStreamLineUiModel(
      sequence: event.sequence,
      eventType: event.eventType,
      displayText: displayTextForLiveEvent(event),
      requiresUserAction: eventRequiresUserAction(event.payloadSummary),
    );
  }

  PrdConversationMessageUiModel? conversationMessageFromPersistedEvent(
    StreamEventEntity event,
  ) {
    if (!_isConversationAgentEventType(event.eventType)) {
      return null;
    }
    final String summary = event.payloadSummary;
    if (summary.isEmpty) {
      return null;
    }
    return PrdConversationMessageUiModel(
      role: PrdConversationMessageRole.agent,
      displayText: summary,
      timestamp: event.timestamp,
      sequence: event.sequence,
    );
  }

  PrdConversationMessageUiModel? conversationMessageFromLiveEvent(
    PrdStreamEvent event,
  ) {
    if (!_isConversationAgentEventType(event.eventType)) {
      return null;
    }
    final String? summary = event.payloadSummary;
    if (summary == null || summary.isEmpty) {
      return null;
    }
    return PrdConversationMessageUiModel(
      role: PrdConversationMessageRole.agent,
      displayText: summary,
      timestamp: event.timestamp,
      sequence: event.sequence,
    );
  }

  String displayTextForPersistedEvent(StreamEventEntity event) {
    if (event.payloadSummary.isNotEmpty) {
      return event.payloadSummary;
    }
    return _fallbackDisplayText(event.eventType);
  }

  String displayTextForLiveEvent(PrdStreamEvent event) {
    final String? summary = event.payloadSummary;
    if (summary != null && summary.isNotEmpty) {
      return summary;
    }
    return _fallbackDisplayText(event.eventType);
  }

  bool eventRequiresUserAction(String? payloadSummary) {
    if (payloadSummary == null || payloadSummary.isEmpty) {
      return false;
    }
    final String normalized = payloadSummary.toUpperCase();
    return normalized.contains('USER_ACTION') ||
        normalized.contains('AWAITING') ||
        normalized.contains('INPUT_REQUIRED');
  }

  bool isTerminalStreamEvent({
    required String eventType,
    String? payloadSummary,
  }) {
    if (eventType == 'done') {
      return true;
    }
    if (eventType == 'result') {
      return payloadSummary != null &&
          payloadSummary.toUpperCase().contains('FINISHED');
    }
    return false;
  }

  bool _isConversationAgentEventType(String eventType) {
    return eventType == 'assistant' || eventType == 'result';
  }

  String _fallbackDisplayText(String eventType) {
    return switch (eventType) {
      'status' => OrchestratorStrings.prdWorkflowStreamEventStatus,
      'assistant' => OrchestratorStrings.prdWorkflowStreamEventAssistant,
      'thinking' => OrchestratorStrings.prdWorkflowStreamEventThinking,
      'tool_call' => OrchestratorStrings.prdWorkflowStreamEventToolCall,
      'done' => OrchestratorStrings.prdWorkflowStreamEventDone,
      'heartbeat' => OrchestratorStrings.prdWorkflowStreamEventHeartbeat,
      _ => OrchestratorStrings.prdWorkflowStreamEventGeneric,
    };
  }

  int _runFeedbackConversationSequence(List<StreamEventEntity> cappedEvents) {
    if (cappedEvents.isEmpty) {
      return _workflowDirectiveConversationSequence + 1;
    }
    final int maxSequence = cappedEvents
        .map((StreamEventEntity event) => event.sequence)
        .reduce((int a, int b) => a > b ? a : b);
    return maxSequence + 1;
  }

  DateTime _timestampForUserMessage(
    List<StreamEventEntity> cappedEvents, {
    required bool preferFirst,
  }) {
    if (cappedEvents.isEmpty) {
      return DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
    }
    return preferFirst
        ? cappedEvents.first.timestamp
        : cappedEvents.last.timestamp;
  }

  PrdConversationMessageUiModel _userConversationMessage({
    required String displayText,
    required int sequence,
    required DateTime timestamp,
  }) {
    return PrdConversationMessageUiModel(
      role: PrdConversationMessageRole.user,
      displayText: displayText,
      timestamp: timestamp,
      sequence: sequence,
    );
  }

  String? _nonEmpty(String? value) {
    if (value == null || value.isEmpty) {
      return null;
    }
    return value;
  }
}
