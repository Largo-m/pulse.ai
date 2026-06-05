import 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart';

export 'package:pulse_ai/features/orchestrator/domain/service/local_git_branches_service.dart'
    show LocalGitBranchesOutcome, LocalGitBranchesResult;

final class ListLocalGitBranchesUseCase {
  ListLocalGitBranchesUseCase({required LocalGitBranchesService service})
    : _service = service;

  final LocalGitBranchesService _service;

  Future<LocalGitBranchesResult> call({
    required String absolutePath,
    String? macosSecurityScopedBookmark,
  }) {
    return _service.listLocalBranches(
      absolutePath,
      macosSecurityScopedBookmark: macosSecurityScopedBookmark,
    );
  }
}
