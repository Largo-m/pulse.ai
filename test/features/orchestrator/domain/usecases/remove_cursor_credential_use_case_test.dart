import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/remove_cursor_credential_use_case.dart';

import '../service/fakes/fake_cursor_credential_store_service.dart';

void main() {
  group('RemoveCursorCredentialUseCase', () {
    test('removes credential from store', () async {
      final FakeCursorCredentialStoreService store =
          FakeCursorCredentialStoreService()..storedCredential = 'stored-key';
      final RemoveCursorCredentialUseCase useCase =
          RemoveCursorCredentialUseCase(credentialStore: store);

      await useCase();

      expect(store.storedCredential, isNull);
    });
  });
}
