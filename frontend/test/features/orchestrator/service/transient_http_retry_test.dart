import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client.dart';
import 'package:pulse_ai/features/orchestrator/service/transient_http_retry.dart';

void main() {
  group('TransientHttpRetry', () {
    test('retries until non-5xx response and bounds attempts', () async {
      const TransientHttpRetry retry = TransientHttpRetry(maxAttempts: 3);
      int callCount = 0;

      final CursorHttpResponse response = await retry.execute(() async {
        callCount++;
        if (callCount < 3) {
          return const CursorHttpResponse(statusCode: 503, body: '{}');
        }
        return const CursorHttpResponse(statusCode: 200, body: '{}');
      });

      expect(callCount, 3);
      expect(response.statusCode, 200);
    });

    test('returns last 5xx when all attempts are retryable', () async {
      const TransientHttpRetry retry = TransientHttpRetry(maxAttempts: 2);
      int callCount = 0;

      final CursorHttpResponse response = await retry.execute(() async {
        callCount++;
        return const CursorHttpResponse(statusCode: 500, body: '{}');
      });

      expect(callCount, 2);
      expect(response.statusCode, 500);
    });

    test('recovers after transient exception before success', () async {
      const TransientHttpRetry retry = TransientHttpRetry(maxAttempts: 3);
      int callCount = 0;

      final CursorHttpResponse response = await retry.execute(() async {
        callCount++;
        if (callCount == 1) {
          throw Exception('temporary');
        }
        return const CursorHttpResponse(statusCode: 200, body: '{}');
      });

      expect(callCount, 2);
      expect(response.statusCode, 200);
    });

    test('rethrows state error without wrapping', () async {
      const TransientHttpRetry retry = TransientHttpRetry(maxAttempts: 1);

      expect(
        () => retry.execute(() async {
          throw StateError('boom');
        }),
        throwsA(isA<StateError>()),
      );
    });

    test('rethrows exception when call keeps failing with errors', () async {
      const TransientHttpRetry retry = TransientHttpRetry(maxAttempts: 2);

      expect(
        () => retry.execute(() async {
          throw Exception('network down');
        }),
        throwsA(isA<Exception>()),
      );
    });
  });
}
