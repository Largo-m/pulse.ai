import 'package:bloc_test/bloc_test.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
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
      slug: 'bot-sre-01',
    );

    final WorkflowEntity workflow = WorkflowEntity(
      projectId: 'project-1',
      slug: 'bot-sre-01',
      branchName: 'main',
      directive: 'Monitorar SLOs',
      prdPhaseStatus: PrdPhaseStatus.draft,
      createdAt: DateTime.utc(2026, 5, 20),
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'starts on welcome view without active agent',
      build: OrchestratorMainContentCubit.new,
      verify: (OrchestratorMainContentCubit cubit) {
        expect(cubit.state.view, OrchestratorMainContentView.welcome);
        expect(cubit.state.activeAgent, isNull);
        expect(cubit.state.activeWorkflow, isNull);
      },
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'showPrdWorkflow exposes prd view with payload slug and projectId',
      build: OrchestratorMainContentCubit.new,
      act: (OrchestratorMainContentCubit cubit) =>
          cubit.showPrdWorkflow(agent: payload, workflow: workflow),
      expect: () => <OrchestratorMainContentState>[
        OrchestratorMainContentState(
          view: OrchestratorMainContentView.prdWorkflow,
          activeAgent: payload,
          activeWorkflow: workflow,
        ),
      ],
      verify: (OrchestratorMainContentCubit cubit) {
        expect(cubit.state.activeAgent?.slug, 'bot-sre-01');
        expect(cubit.state.activeAgent?.projectId, 'project-1');
      },
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'showTechspecWorkflow exposes techspec view with submitted agent',
      build: OrchestratorMainContentCubit.new,
      act: (OrchestratorMainContentCubit cubit) =>
          cubit.showTechspecWorkflow(agent: payload, workflow: workflow),
      expect: () => <OrchestratorMainContentState>[
        OrchestratorMainContentState(
          view: OrchestratorMainContentView.techspecWorkflow,
          activeAgent: payload,
          activeWorkflow: workflow,
        ),
      ],
    );

    final WorkflowEntity approvedWorkflow = WorkflowEntity(
      projectId: 'project-1',
      slug: 'bot-sre-01',
      branchName: 'main',
      prdPhaseStatus: PrdPhaseStatus.approved,
      createdAt: DateTime.utc(2026, 5, 20),
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'openWorkflowFromSidebar exposes prd view for non-approved workflow',
      build: OrchestratorMainContentCubit.new,
      act: (OrchestratorMainContentCubit cubit) =>
          cubit.openWorkflowFromSidebar(workflow),
      verify: (OrchestratorMainContentCubit cubit) {
        expect(cubit.state.view, OrchestratorMainContentView.prdWorkflow);
        expect(cubit.state.activeWorkflow, workflow);
        expect(cubit.state.activeAgent?.slug, workflow.slug);
        expect(cubit.state.activeAgent?.projectId, workflow.projectId);
      },
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'openWorkflowFromSidebar exposes techspec view when prd is approved',
      build: OrchestratorMainContentCubit.new,
      act: (OrchestratorMainContentCubit cubit) =>
          cubit.openWorkflowFromSidebar(approvedWorkflow),
      verify: (OrchestratorMainContentCubit cubit) {
        expect(cubit.state.view, OrchestratorMainContentView.techspecWorkflow);
        expect(cubit.state.activeWorkflow, approvedWorkflow);
        expect(cubit.state.activeAgent?.slug, approvedWorkflow.slug);
      },
    );

    blocTest<OrchestratorMainContentCubit, OrchestratorMainContentState>(
      'showWelcome returns to welcome view and clears active agent',
      build: OrchestratorMainContentCubit.new,
      seed: () => OrchestratorMainContentState(
        view: OrchestratorMainContentView.prdWorkflow,
        activeAgent: payload,
        activeWorkflow: workflow,
      ),
      act: (OrchestratorMainContentCubit cubit) => cubit.showWelcome(),
      expect: () => <OrchestratorMainContentState>[
        const OrchestratorMainContentState(),
      ],
    );
  });
}
