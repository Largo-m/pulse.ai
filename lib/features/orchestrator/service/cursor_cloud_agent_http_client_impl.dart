import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client.dart';

final class CursorCloudAgentHttpClientImpl
    implements CursorCloudAgentHttpClient {
  CursorCloudAgentHttpClientImpl({
    required CursorCredentialStoreService credentialStore,
    Dio? dio,
    String baseUrl = 'https://api.cursor.com',
  }) : _credentialStore = credentialStore,
       _dio =
           dio ??
           Dio(
             BaseOptions(
               baseUrl: baseUrl,
               headers: <String, String>{
                 'Accept': 'application/json',
                 'Content-Type': 'application/json',
               },
               validateStatus: (_) => true,
             ),
           );

  final CursorCredentialStoreService _credentialStore;
  final Dio _dio;

  String _basicAuthToken(String apiKey) {
    return base64Encode(utf8.encode('${apiKey.trim()}:'));
  }

  Future<void> _ensureAuthorization() async {
    final String? apiKey = await _credentialStore.read();
    if (apiKey == null || apiKey.trim().isEmpty) {
      throw StateError('Cursor API credential is missing');
    }
    _dio.options.headers['Authorization'] = 'Basic ${_basicAuthToken(apiKey)}';
  }

  @override
  Future<CursorHttpResponse> get(
    String path, {
    Map<String, String>? headers,
    String? credential,
  }) async {
    final Map<String, String> requestHeaders = <String, String>{...?headers};
    if (credential != null) {
      requestHeaders['Authorization'] = 'Basic ${_basicAuthToken(credential)}';
    } else {
      await _ensureAuthorization();
    }
    final Response<String> response = await _dio.get<String>(
      path,
      options: Options(headers: requestHeaders),
    );
    return CursorHttpResponse(
      statusCode: response.statusCode ?? 0,
      body: response.data ?? '',
    );
  }

  @override
  Future<CursorHttpResponse> post(
    String path, {
    Map<String, String>? headers,
    String? body,
  }) async {
    await _ensureAuthorization();
    final Response<String> response = await _dio.post<String>(
      path,
      data: body,
      options: Options(headers: headers),
    );
    return CursorHttpResponse(
      statusCode: response.statusCode ?? 0,
      body: response.data ?? '',
    );
  }

  @override
  Stream<String> getSseLines(
    String path, {
    Map<String, String>? headers,
  }) async* {
    await _ensureAuthorization();
    final Response<ResponseBody> response = await _dio.get<ResponseBody>(
      path,
      options: Options(
        headers: <String, String>{'Accept': 'text/event-stream', ...?headers},
        responseType: ResponseType.stream,
      ),
    );

    await for (final String line in const LineSplitter().bind(
      utf8.decoder.bind(response.data!.stream),
    )) {
      yield line;
    }
  }
}
