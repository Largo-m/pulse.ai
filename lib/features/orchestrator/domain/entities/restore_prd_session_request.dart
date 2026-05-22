import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';

final class RestorePrdSessionRequest {
  const RestorePrdSessionRequest({
    required this.workflowKey,
    required this.workflowDirective,
    this.workflow,
  });

  final String workflowKey;
  final String? workflowDirective;
  final WorkflowEntity? workflow;
}
