import 'package:git2dart/git2dart.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_origin_remote_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/project_sandbox_access_service.dart';
import 'package:pulse_ai/features/orchestrator/service/github_remote_url_normalizer.dart';

typedef RepositoryOpener = Repository Function(String path);

final class LocalGitOriginRemoteServiceImpl
    implements LocalGitOriginRemoteService {
  LocalGitOriginRemoteServiceImpl({
    ProjectSandboxAccessService? sandboxAccessService,
    RepositoryOpener? openRepository,
  }) : _sandboxAccessService = sandboxAccessService,
       _openRepository = openRepository ?? Repository.open;

  final ProjectSandboxAccessService? _sandboxAccessService;
  final RepositoryOpener _openRepository;

  @override
  Future<LocalGitOriginRemoteResult> resolveOriginRemoteUrl(
    String absolutePath, {
    String? macosSecurityScopedBookmark,
  }) async {
    if (absolutePath.trim().isEmpty) {
      return const LocalGitOriginRemoteResult(
        LocalGitOriginRemoteOutcome.notGitRepository,
        debugMessage: 'empty path',
      );
    }

    final ProjectSandboxAccessService? sandboxAccess = _sandboxAccessService;
    if (sandboxAccess != null) {
      final bool accessed = await sandboxAccess.startAccess(
        macosSecurityScopedBookmark: macosSecurityScopedBookmark,
      );
      if (!accessed && macosSecurityScopedBookmark != null) {
        return const LocalGitOriginRemoteResult(
          LocalGitOriginRemoteOutcome.permissionDenied,
          debugMessage: 'security scoped bookmark access denied',
        );
      }

      try {
        return _resolveWithRepository(absolutePath);
      } finally {
        await sandboxAccess.stopAccess();
      }
    }

    return _resolveWithRepository(absolutePath);
  }

  LocalGitOriginRemoteResult _resolveWithRepository(String absolutePath) {
    Repository? repository;
    try {
      repository = _openRepository(absolutePath);
      return _readOriginUrl(repository);
    } on ArgumentError catch (error) {
      return LocalGitOriginRemoteResult(
        LocalGitOriginRemoteOutcome.notGitRepository,
        debugMessage: error.toString(),
      );
    } on Object catch (error) {
      return LocalGitOriginRemoteResult(
        LocalGitOriginRemoteOutcome.failure,
        debugMessage: error.toString(),
      );
    } finally {
      repository?.free();
    }
  }

  LocalGitOriginRemoteResult _readOriginUrl(Repository repository) {
    final List<String> remoteNames = repository.remotes;
    if (!remoteNames.contains('origin')) {
      return const LocalGitOriginRemoteResult(
        LocalGitOriginRemoteOutcome.remoteNotFound,
        debugMessage: 'origin remote missing',
      );
    }

    final Remote origin = Remote.lookup(repo: repository, name: 'origin');
    try {
      final String? githubUrl = normalizeToGithubHttpsUrl(origin.url);
      if (githubUrl == null) {
        return const LocalGitOriginRemoteResult(
          LocalGitOriginRemoteOutcome.unsupportedHost,
          debugMessage:
              'remote url is not a GitHub HTTPS or git@github.com URL',
        );
      }

      return LocalGitOriginRemoteResult(
        LocalGitOriginRemoteOutcome.success,
        githubHttpsUrl: githubUrl,
      );
    } finally {
      origin.free();
    }
  }
}
