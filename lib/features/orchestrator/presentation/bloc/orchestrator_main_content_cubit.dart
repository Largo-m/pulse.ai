import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

final class OrchestratorMainContentCubit
    extends Cubit<OrchestratorMainContentState> {
  OrchestratorMainContentCubit() : super(const OrchestratorMainContentState());

  void showPrdWorkflow({
    required InitializeAgentSubmitPayload agent,
    required WorkflowEntity workflow,
  }) {
    emit(
      OrchestratorMainContentState(
        view: OrchestratorMainContentView.prdWorkflow,
        activeAgent: agent,
        activeWorkflow: workflow,
      ),
    );
  }

  void showTechspecWorkflow({
    required InitializeAgentSubmitPayload agent,
    WorkflowEntity? workflow,
  }) {
    emit(
      OrchestratorMainContentState(
        view: OrchestratorMainContentView.techspecWorkflow,
        activeAgent: agent,
        activeWorkflow: workflow ?? state.activeWorkflow,
      ),
    );
  }

  void showWelcome() {
    emit(const OrchestratorMainContentState());
  }
}
