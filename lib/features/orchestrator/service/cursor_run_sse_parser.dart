import 'dart:convert';

import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';

final class CursorRunSseParser {
  const CursorRunSseParser();

  List<PrdStreamEvent> parseLines({
    required String cloudRunId,
    required Iterable<String> lines,
    required DateTime startedAt,
  }) {
    final List<PrdStreamEvent> events = <PrdStreamEvent>[];
    String? eventName;
    final StringBuffer dataBuffer = StringBuffer();
    int sequence = 0;

    void emitBuffered() {
      if (eventName == null) {
        dataBuffer.clear();
        return;
      }
      sequence++;
      events.add(
        _mapEvent(
          cloudRunId: cloudRunId,
          eventType: eventName!,
          dataJson: dataBuffer.toString(),
          sequence: sequence,
          timestamp: startedAt.add(Duration(milliseconds: sequence)),
        ),
      );
      eventName = null;
      dataBuffer.clear();
    }

    for (final String rawLine in lines) {
      final String line = rawLine.trimRight();
      if (line.isEmpty) {
        emitBuffered();
        continue;
      }
      if (line.startsWith(':')) {
        continue;
      }
      if (line.startsWith('event:')) {
        emitBuffered();
        eventName = line.substring('event:'.length).trim();
        continue;
      }
      if (line.startsWith('data:')) {
        if (dataBuffer.isNotEmpty) {
          dataBuffer.write('\n');
        }
        dataBuffer.write(line.substring('data:'.length).trim());
        continue;
      }
      if (line.startsWith('id:')) {
        continue;
      }
    }

    emitBuffered();
    return events;
  }

  PrdStreamEvent _mapEvent({
    required String cloudRunId,
    required String eventType,
    required String dataJson,
    required int sequence,
    required DateTime timestamp,
  }) {
    String? payloadSummary;
    if (dataJson.isNotEmpty) {
      try {
        final Object? decoded = jsonDecode(dataJson);
        if (decoded is Map<String, dynamic>) {
          payloadSummary = _summarizePayload(eventType, decoded);
        }
      } on FormatException {
        payloadSummary = null;
      }
    }

    return PrdStreamEvent(
      runId: cloudRunId,
      eventType: eventType,
      sequence: sequence,
      timestamp: timestamp,
      payloadSummary: payloadSummary,
    );
  }

  String? _summarizePayload(String eventType, Map<String, dynamic> payload) {
    switch (eventType) {
      case 'status':
      case 'result':
        final Object? status = payload['status'];
        return status == null ? null : 'status=$status';
      case 'assistant':
      case 'thinking':
        final Object? text = payload['text'];
        if (text is! String || text.isEmpty) {
          return null;
        }
        return text.length <= 120 ? text : '${text.substring(0, 120)}…';
      case 'tool_call':
        final Object? name = payload['name'];
        final Object? toolStatus = payload['status'];
        return 'tool=${name ?? 'unknown'};status=${toolStatus ?? 'unknown'}';
      case 'error':
        final Object? code = payload['code'];
        return 'error=${code ?? 'unknown'}';
      case 'heartbeat':
      case 'done':
        return null;
      default:
        return null;
    }
  }
}
