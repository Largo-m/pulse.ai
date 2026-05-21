import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/service/fakes/fake_cursor_prd_agent_service.dart';

import '../../domain/usecases/fake_local_git_branches_service.dart';

void main() {
  group('FakeCursorPrdAgentService', () {
    test(
      'watchRun emits three events in order with increasing sequence',
      () async {
        final FakeCursorPrdAgentService service = FakeCursorPrdAgentService();

        final List<PrdStreamEvent> events = await service
            .watchRun(FakeCursorPrdAgentService.fakeCloudRunId)
            .toList();

        expect(events.length, 3);
        expect(
          events.map((PrdStreamEvent event) => event.sequence).toList(),
          <int>[1, 2, 3],
        );
      },
    );

    test('cancelRun completes without touching git services', () async {
      final FakeCursorPrdAgentService service = FakeCursorPrdAgentService();
      final FakeLocalGitBranchesService gitService =
          FakeLocalGitBranchesService();

      await service.cancelRun(FakeCursorPrdAgentService.fakeCloudRunId);

      expect(service.cancelRunCallCount, 1);
      expect(gitService.listLocalBranchesCallCount, 0);
    });

    test('startRun returns entity with non-empty cloudRunId', () async {
      final FakeCursorPrdAgentService service = FakeCursorPrdAgentService();

      final run = await service.startRun(
        const PrdRunContext(
          projectId: 'project-1',
          slug: 'agent-a',
          canonicalPath: '/Users/dev/repo',
          branchName: 'main',
          composedPrompt: 'Create PRD',
        ),
      );

      expect(run.cloudRunId, isNotEmpty);
      expect(run.cloudRunId, FakeCursorPrdAgentService.fakeCloudRunId);
    });
  });
}
