import 'package:git2dart/git2dart.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/project_sandbox_access_service.dart';

typedef RepositoryOpener = Repository Function(String path);
typedef BranchListReader =
    LocalGitBranchesResult Function(Repository repository);

final class LocalGitBranchesServiceImpl implements LocalGitBranchesService {
  LocalGitBranchesServiceImpl({
    ProjectSandboxAccessService? sandboxAccessService,
    RepositoryOpener? openRepository,
    BranchListReader? readBranches,
  }) : _sandboxAccessService = sandboxAccessService,
       _openRepository = openRepository ?? Repository.open,
       _readBranches = readBranches ?? _defaultBranchListReader;

  final ProjectSandboxAccessService? _sandboxAccessService;
  final RepositoryOpener _openRepository;
  final BranchListReader _readBranches;

  @override
  Future<LocalGitBranchesResult> listLocalBranches(
    String absolutePath, {
    String? macosSecurityScopedBookmark,
  }) async {
    if (absolutePath.trim().isEmpty) {
      return const LocalGitBranchesResult(
        LocalGitBranchesOutcome.notGitRepository,
        debugMessage: 'empty path',
      );
    }

    final ProjectSandboxAccessService? sandboxAccess = _sandboxAccessService;
    if (sandboxAccess != null) {
      final bool accessed = await sandboxAccess.startAccess(
        macosSecurityScopedBookmark: macosSecurityScopedBookmark,
      );
      if (!accessed && macosSecurityScopedBookmark != null) {
        return const LocalGitBranchesResult(
          LocalGitBranchesOutcome.permissionDenied,
          debugMessage: 'security scoped bookmark access denied',
        );
      }

      try {
        return await _listWithRepository(absolutePath);
      } finally {
        await sandboxAccess.stopAccess();
      }
    }

    return _listWithRepository(absolutePath);
  }

  Future<LocalGitBranchesResult> _listWithRepository(
    String absolutePath,
  ) async {
    Repository? repository;
    try {
      repository = _openRepository(absolutePath);
      return _readBranches(repository);
    } on ArgumentError catch (error) {
      return LocalGitBranchesResult(
        LocalGitBranchesOutcome.notGitRepository,
        debugMessage: error.toString(),
      );
    } on Object catch (error) {
      return _mapOpenError(error);
    } finally {
      repository?.free();
    }
  }

  static LocalGitBranchesResult _defaultBranchListReader(
    Repository repository,
  ) {
    final List<String> branches = repository.branchesLocal
        .map((Branch branch) => branch.name)
        .toList();
    final String? headBranchName =
        repository.isHeadDetached || repository.isBranchUnborn
        ? null
        : repository.head.shorthand;
    return LocalGitBranchesResult(
      LocalGitBranchesOutcome.success,
      branches: branches,
      headBranchName: headBranchName,
    );
  }

  static LocalGitBranchesResult _mapOpenError(Object error) {
    final String text = error.toString().toLowerCase();
    final bool notGit =
        text.contains('not a git repository') ||
        text.contains('could not find repository') ||
        text.contains('repository not found') ||
        text.contains('git_error_repository');
    if (notGit) {
      return LocalGitBranchesResult(
        LocalGitBranchesOutcome.notGitRepository,
        debugMessage: error.toString(),
      );
    }

    final bool permissionDenied =
        text.contains('permission') ||
        text.contains('entitlement') ||
        text.contains('sandbox') ||
        text.contains('denied') ||
        text.contains('operation not permitted');
    if (permissionDenied) {
      return LocalGitBranchesResult(
        LocalGitBranchesOutcome.permissionDenied,
        debugMessage: error.toString(),
      );
    }

    return LocalGitBranchesResult(
      LocalGitBranchesOutcome.failure,
      debugMessage: error.toString(),
    );
  }
}
