enum LocalGitOriginRemoteOutcome {
  success,
  notGitRepository,
  remoteNotFound,
  unsupportedHost,
  permissionDenied,
  failure,
}

final class LocalGitOriginRemoteResult {
  const LocalGitOriginRemoteResult(
    this.outcome, {
    this.githubHttpsUrl,
    this.debugMessage,
  });

  final LocalGitOriginRemoteOutcome outcome;
  final String? githubHttpsUrl;
  final String? debugMessage;
}

abstract interface class LocalGitOriginRemoteService {
  Future<LocalGitOriginRemoteResult> resolveOriginRemoteUrl(
    String absolutePath, {
    String? macosSecurityScopedBookmark,
  });
}
