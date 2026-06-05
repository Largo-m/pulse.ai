final class PrdRunRequest {
  const PrdRunRequest({
    required this.projectId,
    required this.slug,
    required this.repoPath,
    required this.branchName,
    required this.directive,
    this.feedback,
    this.supersedesRunId,
  });

  final String projectId;
  final String slug;
  final String repoPath;
  final String branchName;
  final String directive;
  final String? feedback;
  final String? supersedesRunId;
}
