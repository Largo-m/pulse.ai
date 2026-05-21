final class InitializeAgentSubmitPayload {
  const InitializeAgentSubmitPayload({
    required this.agentName,
    required this.coreDirective,
    required this.projectId,
    required this.branchName,
    this.slug,
  });

  final String agentName;
  final String coreDirective;
  final String projectId;
  final String branchName;
  final String? slug;
}
