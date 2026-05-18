abstract interface class ProjectSandboxAccessService {
  Future<String?> createBookmark(String absolutePath);

  Future<bool> startAccess({required String? macosSecurityScopedBookmark});

  Future<void> stopAccess();
}
