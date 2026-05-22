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
               connectTimeout: const Duration(seconds: 20),
               receiveTimeout: const Duration(seconds: 20),
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

  Future<Map<String, String>> _authorizationHeaders({
    String? credential,
  }) async {
    final String? apiKey = credential ?? await _credentialStore.read();
    if (apiKey == null || apiKey.trim().isEmpty) {
      throw StateError('Cursor API credential is missing');
    }
    return <String, String>{
      'Authorization': 'Basic ${_basicAuthToken(apiKey)}',
    };
  }

  Map<String, String> _mergeHeaders({
    Map<String, String>? headers,
    required Map<String, String> authorizationHeaders,
  }) {
    return <String, String>{...?headers, ...authorizationHeaders};
  }

  @override
  Future<CursorHttpResponse> get(
    String path, {
    Map<String, String>? headers,
    String? credential,
  }) async {
    final Map<String, String> requestHeaders = _mergeHeaders(
      headers: headers,
      authorizationHeaders: await _authorizationHeaders(credential: credential),
    );
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
    final Map<String, String> requestHeaders = _mergeHeaders(
      headers: headers,
      authorizationHeaders: await _authorizationHeaders(),
    );
    final Response<String> response = await _dio.post<String>(
      path,
      data: body,
      options: Options(headers: requestHeaders),
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
    final Map<String, String> requestHeaders = _mergeHeaders(
      headers: <String, String>{'Accept': 'text/event-stream', ...?headers},
      authorizationHeaders: await _authorizationHeaders(),
    );
    final Response<ResponseBody> response = await _dio.get<ResponseBody>(
      path,
      options: Options(
        headers: requestHeaders,
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
