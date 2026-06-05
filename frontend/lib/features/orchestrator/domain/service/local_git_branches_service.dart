enum LocalGitBranchesOutcome {
  success,
  notGitRepository,
  permissionDenied,
  failure,
}

final class LocalGitBranchesResult {
  const LocalGitBranchesResult(
    this.outcome, {
    this.branches = const <String>[],
    this.headBranchName,
    this.debugMessage,
  });

  final LocalGitBranchesOutcome outcome;
  final List<String> branches;
  final String? headBranchName;
  final String? debugMessage;
}

abstract interface class LocalGitBranchesService {
  Future<LocalGitBranchesResult> listLocalBranches(
    String absolutePath, {
    String? macosSecurityScopedBookmark,
  });
}
