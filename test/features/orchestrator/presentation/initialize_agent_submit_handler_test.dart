import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_submit_handler.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

void main() {
  group('InitializeAgentSubmitHandler', () {
    const InitializeAgentSubmitPayload payload = InitializeAgentSubmitPayload(
      agentName: 'Bot-SRE-01',
      coreDirective: 'Monitorar alertas',
      projectId: '/Users/dev/team-repo',
      branchName: 'main',
    );

    test('handle opens techspec workflow for submitted agent', () {
      final OrchestratorMainContentCubit cubit = OrchestratorMainContentCubit();

      InitializeAgentSubmitHandler.handle(cubit, payload);

      expect(cubit.state.view, OrchestratorMainContentView.techspecWorkflow);
      expect(cubit.state.activeAgent, payload);

      cubit.close();
    });
  });
}
