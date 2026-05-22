import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_agent_http_client_impl.dart';

import '../domain/service/fakes/fake_cursor_credential_store_service.dart';

void main() {
  group('CursorCloudAgentHttpClientImpl', () {
    late FakeCursorCredentialStoreService credentialStore;

    setUp(() {
      credentialStore = FakeCursorCredentialStoreService();
    });

    test(
      'get with credential uses draft key in Authorization header',
      () async {
        final List<Map<String, dynamic>> capturedHeaders =
            <Map<String, dynamic>>[];
        final Dio dio = Dio(
          BaseOptions(
            baseUrl: 'https://api.cursor.com',
            validateStatus: (_) => true,
          ),
        );
        dio.interceptors.add(
          InterceptorsWrapper(
            onRequest:
                (RequestOptions options, RequestInterceptorHandler handler) {
                  capturedHeaders.add(
                    Map<String, dynamic>.from(options.headers),
                  );
                  handler.resolve(
                    Response<String>(
                      requestOptions: options,
                      statusCode: 200,
                      data: '{}',
                    ),
                  );
                },
          ),
        );

        final CursorCloudAgentHttpClientImpl client =
            CursorCloudAgentHttpClientImpl(
              credentialStore: credentialStore,
              dio: dio,
            );

        await client.get('/v1/me', credential: 'draft-key-123');

        expect(capturedHeaders, hasLength(1));
        expect(capturedHeaders.single['Authorization'], startsWith('Basic '));
        expect(credentialStore.storedCredential, isNull);
      },
    );

    test('get without credential reads stored key for Authorization', () async {
      credentialStore.storedCredential = 'stored-key';
      final List<Map<String, dynamic>> capturedHeaders =
          <Map<String, dynamic>>[];
      final Dio dio = Dio(
        BaseOptions(
          baseUrl: 'https://api.cursor.com',
          validateStatus: (_) => true,
        ),
      );
      dio.interceptors.add(
        InterceptorsWrapper(
          onRequest:
              (RequestOptions options, RequestInterceptorHandler handler) {
                capturedHeaders.add(Map<String, dynamic>.from(options.headers));
                handler.resolve(
                  Response<String>(
                    requestOptions: options,
                    statusCode: 200,
                    data: '{}',
                  ),
                );
              },
        ),
      );

      final CursorCloudAgentHttpClientImpl client =
          CursorCloudAgentHttpClientImpl(
            credentialStore: credentialStore,
            dio: dio,
          );

      await client.get('/v1/me');

      expect(credentialStore.storedCredential, 'stored-key');
      expect(capturedHeaders.single['Authorization'], startsWith('Basic '));
    });
  });
}
