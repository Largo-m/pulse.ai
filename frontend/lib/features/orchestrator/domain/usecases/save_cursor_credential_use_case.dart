import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';

final class SaveCursorCredentialUseCase {
  SaveCursorCredentialUseCase({
    required CursorCredentialStoreService credentialStore,
  }) : _credentialStore = credentialStore;

  final CursorCredentialStoreService _credentialStore;

  Future<void> call(String apiKey) {
    return _credentialStore.write(apiKey);
  }
}
