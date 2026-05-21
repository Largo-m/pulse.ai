import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/recent_project_tree_agent_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/recent_project_sidebar_workflows_mapper.dart';

void main() {
  group('mapWorkflowsToSidebarAgents', () {
    final DateTime createdAt = DateTime.utc(2026, 5, 20);

    final List<WorkflowEntity> workflows = <WorkflowEntity>[
      WorkflowEntity(
        projectId: 'project-1',
        slug: 'alpha-flow',
        branchName: 'main',
        prdPhaseStatus: PrdPhaseStatus.draft,
        createdAt: createdAt,
      ),
      WorkflowEntity(
        projectId: 'project-1',
        slug: 'beta-flow',
        branchName: 'develop',
        prdPhaseStatus: PrdPhaseStatus.running,
        createdAt: createdAt,
      ),
    ];

    test('maps two workflows to two sidebar entries', () {
      final List<RecentProjectTreeAgentUiModel> agents =
          mapWorkflowsToSidebarAgents(
            workflows: workflows,
            activeSlug: 'alpha-flow',
          );

      expect(agents, hasLength(2));
      expect(agents.first.displayName, 'alpha-flow');
      expect(agents.first.isActive, isTrue);
      expect(agents.last.displayName, 'beta-flow');
      expect(agents.last.isActive, isFalse);
      expect(agents.last.isRunning, isTrue);
    });

    test('marks no agent active when activeSlug is null', () {
      final List<RecentProjectTreeAgentUiModel> agents =
          mapWorkflowsToSidebarAgents(workflows: workflows, activeSlug: null);

      expect(
        agents.every((RecentProjectTreeAgentUiModel a) => !a.isActive),
        isTrue,
      );
    });
  });
}
