import 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart';

final class FakeLocalGitBranchesService implements LocalGitBranchesService {
  LocalGitBranchesResult nextResult = const LocalGitBranchesResult(
    LocalGitBranchesOutcome.success,
  );

  final Map<String, LocalGitBranchesResult> resultsByPath =
      <String, LocalGitBranchesResult>{};
  final Map<String, Duration> delaysByPath = <String, Duration>{};

  int listLocalBranchesCallCount = 0;
  String? lastAbsolutePath;
  String? lastMacosSecurityScopedBookmark;

  @override
  Future<LocalGitBranchesResult> listLocalBranches(
    String absolutePath, {
    String? macosSecurityScopedBookmark,
  }) async {
    listLocalBranchesCallCount++;
    lastAbsolutePath = absolutePath;
    lastMacosSecurityScopedBookmark = macosSecurityScopedBookmark;

    final Duration? delay = delaysByPath[absolutePath];
    if (delay != null) {
      await Future<void>.delayed(delay);
    }

    return resultsByPath[absolutePath] ?? nextResult;
  }
}
