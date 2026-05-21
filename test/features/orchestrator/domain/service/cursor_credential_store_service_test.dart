import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';

import 'fakes/fake_cursor_credential_store_service.dart';

void main() {
  group('FakeCursorCredentialStoreService', () {
    late CursorCredentialStoreService store;

    setUp(() {
      store = FakeCursorCredentialStoreService();
    });

    test('save then read returns the same credential', () async {
      await store.write('cursor-api-key-test');

      final String? read = await store.read();

      expect(read, 'cursor-api-key-test');
    });

    test('delete clears stored credential', () async {
      await store.write('cursor-api-key-test');
      await store.delete();

      final String? read = await store.read();

      expect(read, isNull);
    });
  });
}
