import 'dart:async';

import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client.dart';

typedef CursorHttpCall = Future<CursorHttpResponse> Function();

final class TransientHttpRetry {
  const TransientHttpRetry({
    this.maxAttempts = 3,
    this.initialDelay = const Duration(milliseconds: 200),
  });

  final int maxAttempts;
  final Duration initialDelay;

  Future<CursorHttpResponse> execute(CursorHttpCall call) async {
    CursorHttpResponse? lastResponse;
    Object? lastError;

    for (int attempt = 0; attempt < maxAttempts; attempt++) {
      try {
        final CursorHttpResponse response = await call();
        lastResponse = response;
        if (!_isRetryableStatus(response.statusCode)) {
          return response;
        }
      } on Object catch (error) {
        lastError = error;
      }

      if (attempt < maxAttempts - 1) {
        final int multiplier = 1 << attempt;
        await Future<void>.delayed(initialDelay * multiplier);
      }
    }

    if (lastResponse != null) {
      return lastResponse;
    }
    if (lastError is Exception) {
      throw lastError;
    }
    if (lastError is Error) {
      throw lastError;
    }
    throw Exception('HTTP retry exhausted without response');
  }

  bool _isRetryableStatus(int statusCode) {
    return statusCode >= 500 && statusCode < 600;
  }
}
