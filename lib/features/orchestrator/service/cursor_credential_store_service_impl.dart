import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_credential_store_service.dart';

final class CursorCredentialStoreServiceImpl
    implements CursorCredentialStoreService {
  CursorCredentialStoreServiceImpl({FlutterSecureStorage? storage})
    : _storage =
          storage ??
          const FlutterSecureStorage(
            mOptions: MacOsOptions(useDataProtectionKeyChain: false),
          );

  static const String _storageKey = 'cursor_prd_agent_credential';

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read() {
    return _storage.read(key: _storageKey);
  }

  @override
  Future<void> write(String credential) {
    return _storage.write(key: _storageKey, value: credential);
  }

  @override
  Future<void> delete() {
    return _storage.delete(key: _storageKey);
  }
}
