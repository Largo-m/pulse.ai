import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

void main() {
  group('OrchestratorMainContentCubit', () {
    const InitializeAgentSubmitPayload payload = InitializeAgentSubmitPayload(
      agentName: 'Bot-SRE-01',
      coreDirective: 'Monitorar SLOs',
      projectId: 'project-1',
      branchName: 'main',
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'starts on welcome view without active agent',
      build: OrchestratorMainContentCubit.new,
      verify: (OrchestratorMainContentCubit cubit) {
        expect(cubit.state.view, OrchestratorMainContentView.welcome);
        expect(cubit.state.activeAgent, isNull);
      },
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'showTechspecWorkflow exposes techspec view with submitted agent',
      build: OrchestratorMainContentCubit.new,
      act: (OrchestratorMainContentCubit cubit) =>
          cubit.showTechspecWorkflow(payload),
      expect: () => <OrchestratorMainContentState>[
        const OrchestratorMainContentState(
          view: OrchestratorMainContentView.techspecWorkflow,
          activeAgent: payload,
        ),
      ],
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'showWelcome returns to welcome view and clears active agent',
      build: OrchestratorMainContentCubit.new,
      seed: () => const OrchestratorMainContentState(
        view: OrchestratorMainContentView.techspecWorkflow,
        activeAgent: payload,
      ),
      act: (OrchestratorMainContentCubit cubit) => cubit.showWelcome(),
      expect: () => <OrchestratorMainContentState>[
        const OrchestratorMainContentState(),
      ],
    );
  });
}
