import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_run_sse_parser.dart';

void main() {
  group('CursorRunSseParser', () {
    const CursorRunSseParser parser = CursorRunSseParser();
    final DateTime startedAt = DateTime.utc(2026, 5, 20, 12);

    test('maps fixture stream to ordered events with increasing sequence', () {
      final File fixture = File('test/fixtures/cursor/run_stream.sse');
      final List<String> lines = fixture.readAsLinesSync();

      final List<PrdStreamEvent> events = parser
          .parseLines(
            cloudRunId: 'bc-agent::run-fake-001',
            lines: lines,
            startedAt: startedAt,
          )
          .toList();

      expect(events.length, 3);
      expect(
        events.map((PrdStreamEvent event) => event.sequence).toList(),
        <int>[1, 2, 3],
      );
      expect(events.first.eventType, 'status');
      expect(events.elementAt(1).eventType, 'assistant');
      expect(events.last.eventType, 'done');
      expect(events.first.payloadSummary, contains('RUNNING'));
    });
  });
}
