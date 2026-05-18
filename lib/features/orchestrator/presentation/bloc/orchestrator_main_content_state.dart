import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

enum OrchestratorMainContentView { welcome, techspecWorkflow }

final class OrchestratorMainContentState {
  const OrchestratorMainContentState({
    this.view = OrchestratorMainContentView.welcome,
    this.activeAgent,
  });

  final OrchestratorMainContentView view;
  final InitializeAgentSubmitPayload? activeAgent;

  OrchestratorMainContentState copyWith({
    OrchestratorMainContentView? view,
    InitializeAgentSubmitPayload? activeAgent,
    bool clearActiveAgent = false,
  }) {
    return OrchestratorMainContentState(
      view: view ?? this.view,
      activeAgent: clearActiveAgent ? null : activeAgent ?? this.activeAgent,
    );
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is OrchestratorMainContentState &&
            other.view == view &&
            other.activeAgent == activeAgent;
  }

  @override
  int get hashCode => Object.hash(view, activeAgent);
}
