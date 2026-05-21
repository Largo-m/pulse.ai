import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';

final class FakeCursorCredentialStoreService
    implements CursorCredentialStoreService {
  String? storedCredential;

  @override
  Future<String?> read() async {
    return storedCredential;
  }

  @override
  Future<void> write(String credential) async {
    storedCredential = credential;
  }

  @override
  Future<void> delete() async {
    storedCredential = null;
  }
}
