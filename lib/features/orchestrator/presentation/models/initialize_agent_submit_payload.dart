final class InitializeAgentSubmitPayload {
  const InitializeAgentSubmitPayload({
    required this.agentName,
    required this.coreDirective,
    required this.projectId,
    required this.branchName,
  });

  final String agentName;
  final String coreDirective;
  final String projectId;
  final String branchName;
}
