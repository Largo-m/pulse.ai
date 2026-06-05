import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';

final class FakeCursorCredentialStoreService
    implements CursorCredentialStoreService {
  String? storedCredential;
  Object? throwOnWrite;
  Object? throwOnDelete;

  @override
  Future<String?> read() async {
    return storedCredential;
  }

  @override
  Future<void> write(String credential) async {
    final Object? error = throwOnWrite;
    if (error != null) {
      Error.throwWithStackTrace(error, StackTrace.current);
    }
    storedCredential = credential;
  }

  @override
  Future<void> delete() async {
    final Object? error = throwOnDelete;
    if (error != null) {
      Error.throwWithStackTrace(error, StackTrace.current);
    }
    storedCredential = null;
  }
}
