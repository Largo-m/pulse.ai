import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/create_workflow_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_recent_projects_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/select_active_project_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/orchestrator_main_content_state.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/recent_projects_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/initialize_agent_submit_handler.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/initialize_agent_submit_payload.dart';

import '../domain/usecases/fake_recent_projects_repository.dart';

void main() {
  group('InitializeAgentSubmitHandler', () {
    const InitializeAgentSubmitPayload payload = InitializeAgentSubmitPayload(
      agentName: 'Bot-SRE-01',
      coreDirective: 'Monitorar alertas',
      projectId: 'project-1',
      branchName: 'main',
      slug: 'bot-sre-01',
    );

    testWidgets('handle opens prd workflow after create workflow succeeds', (
      WidgetTester tester,
    ) async {
      final FakeWorkflowRepository workflowRepository =
          FakeWorkflowRepository();
      final CreateWorkflowUseCase createWorkflowUseCase = CreateWorkflowUseCase(
        workflowRepository: workflowRepository,
      );
      final FakeRecentProjectsRepository recentProjectsRepository =
          FakeRecentProjectsRepository();
      final RecentProjectsCubit recentProjectsCubit = RecentProjectsCubit(
        listRecentProjectsUseCase: ListRecentProjectsUseCase(
          recentProjectsRepository,
        ),
        selectActiveProjectUseCase: SelectActiveProjectUseCase(
          recentProjectsRepository,
        ),
        loadOnCreate: false,
      );
      final OrchestratorMainContentCubit mainContentCubit =
          OrchestratorMainContentCubit();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext context) {
                return ElevatedButton(
                  onPressed: () {
                    unawaited(
                      InitializeAgentSubmitHandler.handle(
                        context: context,
                        mainContentCubit: mainContentCubit,
                        recentProjectsCubit: recentProjectsCubit,
                        createWorkflowUseCase: createWorkflowUseCase,
                        payload: payload,
                      ),
                    );
                  },
                  child: const Text('submit'),
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.text('submit'));
      await tester.pumpAndSettle();

      expect(
        mainContentCubit.state.view,
        OrchestratorMainContentView.prdWorkflow,
      );
      expect(mainContentCubit.state.activeAgent, payload);
      expect(mainContentCubit.state.activeWorkflow?.slug, 'bot-sre-01');
      expect(mainContentCubit.state.activeWorkflow?.projectId, 'project-1');

      await mainContentCubit.close();
      await recentProjectsCubit.close();
    });

    testWidgets('handle keeps welcome view when create workflow fails', (
      WidgetTester tester,
    ) async {
      final FakeWorkflowRepository workflowRepository = FakeWorkflowRepository();
      await workflowRepository.create(
        projectId: 'project-1',
        slug: 'bot-sre-01',
        branchName: 'main',
      );
      final CreateWorkflowUseCase createWorkflowUseCase = CreateWorkflowUseCase(
        workflowRepository: workflowRepository,
      );
      final OrchestratorMainContentCubit mainContentCubit =
          OrchestratorMainContentCubit();
      final RecentProjectsCubit recentProjectsCubit = RecentProjectsCubit(
        listRecentProjectsUseCase: ListRecentProjectsUseCase(
          FakeRecentProjectsRepository(),
        ),
        selectActiveProjectUseCase: SelectActiveProjectUseCase(
          FakeRecentProjectsRepository(),
        ),
        loadOnCreate: false,
      );

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (BuildContext context) {
                return ElevatedButton(
                  onPressed: () {
                    unawaited(
                      InitializeAgentSubmitHandler.handle(
                        context: context,
                        mainContentCubit: mainContentCubit,
                        recentProjectsCubit: recentProjectsCubit,
                        createWorkflowUseCase: createWorkflowUseCase,
                        payload: payload,
                      ),
                    );
                  },
                  child: const Text('submit'),
                );
              },
            ),
          ),
        ),
      );

      await tester.tap(find.text('submit'));
      await tester.pumpAndSettle();

      expect(mainContentCubit.state.view, OrchestratorMainContentView.welcome);
      expect(find.byType(SnackBar), findsOneWidget);

      await mainContentCubit.close();
      await recentProjectsCubit.close();
    });
  });
}
