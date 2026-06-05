import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_run_sse_parser.dart';

void main() {
  group('CursorRunSseParser extended mapping', () {
    const CursorRunSseParser parser = CursorRunSseParser();
    final DateTime startedAt = DateTime.utc(2026, 5, 20);

    test('maps tool_call thinking error and result payloads', () {
      final List<PrdStreamEvent> events = parser.parseLines(
        cloudRunId: 'run-1',
        lines: <String>[
          'event: thinking',
          'data: {"text":"Planning"}',
          '',
          'event: tool_call',
          'data: {"callId":"c1","name":"read_file","status":"running"}',
          '',
          'event: error',
          'data: {"code":"upstream_error","message":"fail"}',
          '',
          'event: result',
          'data: {"runId":"run-1","status":"FINISHED"}',
          '',
        ],
        startedAt: startedAt,
      );

      expect(events.length, 4);
      expect(events[0].eventType, 'thinking');
      expect(events[1].payloadSummary, contains('read_file'));
      expect(events[2].payloadSummary, contains('upstream_error'));
      expect(events[3].payloadSummary, contains('FINISHED'));
    });

    test('maps result payload text field for agent conversation', () {
      final List<PrdStreamEvent> events = parser.parseLines(
        cloudRunId: 'run-1',
        lines: <String>[
          'event: result',
          'data: {"result":"Resposta completa do agente"}',
          '',
        ],
        startedAt: startedAt,
      );

      expect(events.single.payloadSummary, 'Resposta completa do agente');
    });

    test('ignores invalid json payloads without throwing', () {
      final List<PrdStreamEvent> events = parser.parseLines(
        cloudRunId: 'run-1',
        lines: <String>['event: assistant', 'data: not-json', ''],
        startedAt: startedAt,
      );

      expect(events.single.payloadSummary, isNull);
    });
  });
}
