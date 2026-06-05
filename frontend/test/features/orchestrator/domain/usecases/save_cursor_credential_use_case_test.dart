import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/save_cursor_credential_use_case.dart';

import '../service/fakes/fake_cursor_credential_store_service.dart';

void main() {
  group('SaveCursorCredentialUseCase', () {
    test('persists credential via credential store', () async {
      final FakeCursorCredentialStoreService store =
          FakeCursorCredentialStoreService();
      final SaveCursorCredentialUseCase useCase = SaveCursorCredentialUseCase(
        credentialStore: store,
      );

      await useCase('cursor-api-key-to-save');

      expect(store.storedCredential, 'cursor-api-key-to-save');
    });
  });
}
