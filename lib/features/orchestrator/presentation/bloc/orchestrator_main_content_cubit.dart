import 'package:flutter_bloc/flutter_bloc.dart';

import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

final class OrchestratorMainContentCubit
    extends Cubit<OrchestratorMainContentState> {
  OrchestratorMainContentCubit() : super(const OrchestratorMainContentState());

  void showTechspecWorkflow(InitializeAgentSubmitPayload agent) {
    emit(
      OrchestratorMainContentState(
        view: OrchestratorMainContentView.techspecWorkflow,
        activeAgent: agent,
      ),
    );
  }

  void showWelcome() {
    emit(const OrchestratorMainContentState());
  }
}
