import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

abstract final class InitializeAgentSubmitHandler {
  static void handle(
    OrchestratorMainContentCubit mainContentCubit,
    InitializeAgentSubmitPayload payload,
  ) {
    mainContentCubit.showTechspecWorkflow(payload);
  }
}
