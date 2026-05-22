final class CursorHttpResponse {
  const CursorHttpResponse({required this.statusCode, required this.body});

  final int statusCode;
  final String body;
}

abstract interface class CursorCloudAgentHttpClient {
  Future<CursorHttpResponse> get(
    String path, {
    Map<String, String>? headers,
    String? credential,
  });

  Future<CursorHttpResponse> post(
    String path, {
    Map<String, String>? headers,
    String? body,
  });

  Stream<String> getSseLines(String path, {Map<String, String>? headers});
}
