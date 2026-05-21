abstract interface class CursorCredentialStoreService {
  Future<String?> read();

  Future<void> write(String credential);

  Future<void> delete();
}
