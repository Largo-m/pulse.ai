import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/recent_project_tree_agent_ui_model.dart';

List<RecentProjectTreeAgentUiModel> mapWorkflowsToSidebarAgents({
  required List<WorkflowEntity> workflows,
  required String? activeSlug,
}) {
  return workflows
      .map(
        (WorkflowEntity workflow) => RecentProjectTreeAgentUiModel(
          slug: workflow.slug,
          displayName: workflow.slug,
          isActive: workflow.slug == activeSlug,
          isRunning: workflow.prdPhaseStatus == PrdPhaseStatus.running,
        ),
      )
      .toList(growable: false);
}
