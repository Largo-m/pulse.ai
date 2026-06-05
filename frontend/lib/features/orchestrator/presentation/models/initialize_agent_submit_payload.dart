import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';

final class InitializeAgentSubmitPayload {
  const InitializeAgentSubmitPayload({
    required this.agentName,
    required this.coreDirective,
    required this.projectId,
    required this.branchName,
    required this.slug,
  });

  final String agentName;
  final String coreDirective;
  final String projectId;
  final String branchName;
  final String slug;

  factory InitializeAgentSubmitPayload.fromWorkflow(WorkflowEntity workflow) {
    return InitializeAgentSubmitPayload(
      agentName: workflow.slug,
      coreDirective: workflow.directive ?? '',
      projectId: workflow.projectId,
      branchName: workflow.branchName,
      slug: workflow.slug,
    );
  }
}
