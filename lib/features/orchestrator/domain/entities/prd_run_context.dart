final class PrdRunContext {
  const PrdRunContext({
    required this.projectId,
    required this.slug,
    required this.canonicalPath,
    required this.branchName,
    required this.composedPrompt,
    this.macosSecurityScopedBookmark,
    this.supersedesRunId,
    this.feedback,
  });

  final String projectId;
  final String slug;
  final String canonicalPath;
  final String branchName;
  final String composedPrompt;
  final String? macosSecurityScopedBookmark;
  final String? supersedesRunId;
  final String? feedback;
}
