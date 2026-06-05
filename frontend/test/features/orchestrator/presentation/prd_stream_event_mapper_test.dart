import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_conversation_message_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_event_mapper.dart';

void main() {
  const PrdStreamEventMapper mapper = PrdStreamEventMapper();
  final DateTime baseTime = DateTime.utc(2026, 5, 22, 12);

  StreamEventEntity persistedEvent({
    required int sequence,
    required String eventType,
    String payloadSummary = '',
  }) {
    return StreamEventEntity(
      runId: 'run-1',
      sequence: sequence,
      eventType: eventType,
      payloadSummary: payloadSummary,
      timestamp: baseTime.add(Duration(seconds: sequence)),
    );
  }

  PrdStreamEvent liveEvent({
    required int sequence,
    required String eventType,
    String? payloadSummary,
  }) {
    return PrdStreamEvent(
      runId: 'run-1',
      sequence: sequence,
      eventType: eventType,
      timestamp: baseTime.add(Duration(seconds: sequence)),
      payloadSummary: payloadSummary,
    );
  }

  group('PrdStreamEventMapper', () {
    test(
      'maps assistant StreamEventEntity with payloadSummary to agent conversation message',
      () {
        const String summary = 'Resposta do agente';
        final PrdStreamEventMapperResult result = mapper.mapPersistedEvents(
          events: <StreamEventEntity>[
            persistedEvent(
              sequence: 10,
              eventType: 'assistant',
              payloadSummary: summary,
            ),
          ],
        );

        expect(result.conversationMessages, hasLength(1));
        final PrdConversationMessageUiModel message =
            result.conversationMessages.first;
        expect(message.role, PrdConversationMessageRole.agent);
        expect(message.displayText, summary);
        expect(message.sequence, 10);
        expect(message.timestamp, baseTime.add(const Duration(seconds: 10)));
      },
    );

    test(
      'thinking event yields terminal line and no conversation messages',
      () {
        final PrdStreamEventMapperResult result = mapper.mapPersistedEvents(
          events: <StreamEventEntity>[
            persistedEvent(sequence: 3, eventType: 'thinking'),
          ],
        );

        expect(result.terminalLines, hasLength(1));
        expect(result.terminalLines.first.eventType, 'thinking');
        expect(
          result.terminalLines.first.displayText,
          OrchestratorStrings.prdWorkflowStreamEventThinking,
        );
        expect(result.conversationMessages, isEmpty);
      },
    );

    test(
      'workflowDirective and runFeedback produce two user messages with distinct sequences',
      () {
        final PrdStreamEventMapperResult result = mapper.mapPersistedEvents(
          events: const <StreamEventEntity>[],
          workflowDirective: 'Criar PRD',
          runFeedback: 'Ajuste escopo',
        );

        expect(result.conversationMessages, hasLength(2));
        expect(
          result.conversationMessages.every(
            (PrdConversationMessageUiModel message) =>
                message.role == PrdConversationMessageRole.user,
          ),
          isTrue,
        );
        expect(
          result.conversationMessages.map(
            (PrdConversationMessageUiModel message) => message.displayText,
          ),
          <String>['Criar PRD', 'Ajuste escopo'],
        );
        expect(
          result.conversationMessages
              .map((PrdConversationMessageUiModel message) => message.sequence)
              .toSet(),
          hasLength(2),
        );
      },
    );

    test('caps 250 sequential events to the last 200 by sequence', () {
      final List<StreamEventEntity> events = List<StreamEventEntity>.generate(
        250,
        (int index) => persistedEvent(sequence: index + 1, eventType: 'status'),
      );

      final List<StreamEventEntity> capped = mapper.capPersistedEvents(events);

      expect(capped, hasLength(PrdStreamBufferPolicy.maxInMemoryEvents));
      expect(capped.first.sequence, 51);
      expect(capped.last.sequence, 250);

      final PrdStreamEventMapperResult result = mapper.mapPersistedEvents(
        events: events,
      );

      expect(result.terminalLines, hasLength(200));
      expect(result.terminalLines.first.sequence, 51);
      expect(result.terminalLines.last.sequence, 250);
    });

    test(
      'live result event line matches persisted result with same payload',
      () {
        const String summary = 'FINISHED: entrega concluída';
        final PrdStreamLineUiModel liveLine = mapper.mapLiveEventToLine(
          liveEvent(sequence: 42, eventType: 'result', payloadSummary: summary),
        );
        final PrdStreamLineUiModel persistedLine = mapper
            .mapPersistedEventToLine(
              persistedEvent(
                sequence: 42,
                eventType: 'result',
                payloadSummary: summary,
              ),
            );

        expect(liveLine, persistedLine);
      },
    );

    test('excludes tool_call and heartbeat from conversation', () {
      final PrdStreamEventMapperResult result = mapper.mapPersistedEvents(
        events: <StreamEventEntity>[
          persistedEvent(sequence: 1, eventType: 'tool_call'),
          persistedEvent(sequence: 2, eventType: 'heartbeat'),
        ],
      );

      expect(result.terminalLines, hasLength(2));
      expect(result.conversationMessages, isEmpty);
    });

    test('marks line requiresUserAction when summary contains USER_ACTION', () {
      final PrdStreamLineUiModel line = mapper.mapPersistedEventToLine(
        persistedEvent(
          sequence: 5,
          eventType: 'status',
          payloadSummary: 'USER_ACTION: aguardando revisão',
        ),
      );

      expect(line.requiresUserAction, isTrue);
    });

    test('isTerminalStreamEvent returns true for done and FINISHED result', () {
      expect(mapper.isTerminalStreamEvent(eventType: 'done'), isTrue);
      expect(
        mapper.isTerminalStreamEvent(
          eventType: 'result',
          payloadSummary: 'FINISHED',
        ),
        isTrue,
      );
      expect(
        mapper.isTerminalStreamEvent(
          eventType: 'result',
          payloadSummary: 'partial',
        ),
        isFalse,
      );
    });

    test(
      'conversationMessageFromLiveEvent mirrors persisted assistant rules',
      () {
        final PrdConversationMessageUiModel? liveMessage = mapper
            .conversationMessageFromLiveEvent(
              liveEvent(
                sequence: 7,
                eventType: 'assistant',
                payloadSummary: 'Ao vivo',
              ),
            );
        final PrdConversationMessageUiModel? persistedMessage = mapper
            .conversationMessageFromPersistedEvent(
              persistedEvent(
                sequence: 7,
                eventType: 'assistant',
                payloadSummary: 'Ao vivo',
              ),
            );

        expect(liveMessage, persistedMessage);
      },
    );

    test(
      'displayTextForLiveEvent uses fallback label when summary is empty',
      () {
        expect(
          mapper.displayTextForLiveEvent(
            liveEvent(sequence: 1, eventType: 'status'),
          ),
          OrchestratorStrings.prdWorkflowStreamEventStatus,
        );
      },
    );

    test('places runFeedback after stream-derived agent messages', () {
      final PrdStreamEventMapperResult result = mapper.mapPersistedEvents(
        events: <StreamEventEntity>[
          persistedEvent(
            sequence: 100,
            eventType: 'assistant',
            payloadSummary: 'Resposta',
          ),
        ],
        workflowDirective: 'Diretiva',
        runFeedback: 'Feedback',
      );

      expect(
        result.conversationMessages.map(
          (PrdConversationMessageUiModel message) => message.displayText,
        ),
        <String>['Diretiva', 'Resposta', 'Feedback'],
      );
      expect(result.conversationMessages.last.sequence, 101);
    });
  });
}
