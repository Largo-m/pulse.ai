import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

enum OrchestratorMainContentView { welcome, prdWorkflow, techspecWorkflow }

final class OrchestratorMainContentState {
  const OrchestratorMainContentState({
    this.view = OrchestratorMainContentView.welcome,
    this.activeAgent,
    this.activeWorkflow,
  });

  final OrchestratorMainContentView view;
  final InitializeAgentSubmitPayload? activeAgent;
  final WorkflowEntity? activeWorkflow;

  OrchestratorMainContentState copyWith({
    OrchestratorMainContentView? view,
    InitializeAgentSubmitPayload? activeAgent,
    WorkflowEntity? activeWorkflow,
    bool clearActiveAgent = false,
    bool clearActiveWorkflow = false,
  }) {
    return OrchestratorMainContentState(
      view: view ?? this.view,
      activeAgent: clearActiveAgent ? null : activeAgent ?? this.activeAgent,
      activeWorkflow: clearActiveWorkflow
          ? null
          : activeWorkflow ?? this.activeWorkflow,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is OrchestratorMainContentState &&
            other.view == view &&
            other.activeAgent == activeAgent &&
            other.activeWorkflow == activeWorkflow;
  }

  @override
  int get hashCode => Object.hash(view, activeAgent, activeWorkflow);
}
