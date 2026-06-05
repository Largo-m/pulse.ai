import 'package:pulse_ai/features/orchestrator/domain/service/local_git_origin_remote_service.dart';

final class FakeLocalGitOriginRemoteService
    implements LocalGitOriginRemoteService {
  LocalGitOriginRemoteResult nextResult = const LocalGitOriginRemoteResult(
    LocalGitOriginRemoteOutcome.success,
    githubHttpsUrl: 'https://github.com/acme/repo',
  );

  final Map<String, LocalGitOriginRemoteResult> resultsByPath =
      <String, LocalGitOriginRemoteResult>{};

  int resolveOriginRemoteUrlCallCount = 0;
  String? lastAbsolutePath;

  @override
  Future<LocalGitOriginRemoteResult> resolveOriginRemoteUrl(
    String absolutePath, {
    String? macosSecurityScopedBookmark,
  }) async {
    resolveOriginRemoteUrlCallCount++;
    lastAbsolutePath = absolutePath;
    return resultsByPath[absolutePath] ?? nextResult;
  }
}
