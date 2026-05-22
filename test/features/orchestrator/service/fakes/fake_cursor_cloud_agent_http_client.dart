import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client.dart';

final class FakeCursorCloudAgentHttpClient
    implements CursorCloudAgentHttpClient {
  final List<String> getPaths = <String>[];
  final List<String> postPaths = <String>[];
  final List<String> ssePaths = <String>[];

  CursorHttpResponse? nextGetResponse;
  final Map<String, CursorHttpResponse> getResponsesByPath =
      <String, CursorHttpResponse>{};

  CursorHttpResponse? nextPostResponse;
  final List<CursorHttpResponse> postResponseQueue = <CursorHttpResponse>[];
  final Map<String, CursorHttpResponse> postResponsesByPath =
      <String, CursorHttpResponse>{};

  final Map<String, List<String>> sseLinesByPath = <String, List<String>>{};

  int getCallCount = 0;
  int postCallCount = 0;
  String? lastGetCredential;

  @override
  Future<CursorHttpResponse> get(
    String path, {
    Map<String, String>? headers,
    String? credential,
  }) async {
    getCallCount++;
    getPaths.add(path);
    lastGetCredential = credential;
    return getResponsesByPath[path] ??
        nextGetResponse ??
        const CursorHttpResponse(statusCode: 404, body: '{}');
  }

  @override
  Future<CursorHttpResponse> post(
    String path, {
    Map<String, String>? headers,
    String? body,
  }) async {
    postCallCount++;
    postPaths.add(path);
    if (postResponseQueue.isNotEmpty) {
      return postResponseQueue.removeAt(0);
    }
    return postResponsesByPath[path] ??
        nextPostResponse ??
        const CursorHttpResponse(statusCode: 404, body: '{}');
  }

  @override
  Stream<String> getSseLines(
    String path, {
    Map<String, String>? headers,
  }) async* {
    ssePaths.add(path);
    final List<String> lines = sseLinesByPath[path] ?? <String>[];
    for (final String line in lines) {
      yield line;
    }
  }
}
