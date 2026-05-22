import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';

final class RemoveCursorCredentialUseCase {
  RemoveCursorCredentialUseCase({
    required CursorCredentialStoreService credentialStore,
  }) : _credentialStore = credentialStore;

  final CursorCredentialStoreService _credentialStore;

  Future<void> call() {
    return _credentialStore.delete();
  }
}
